"""Minimal Telegram Bot API client + outbox delivery worker.

* The token is read from the environment by the caller and never logged: `redact()` strips it
  from any error text before it is stored or printed.
* "accepted" means the Bot API returned ok=true with a message_id. That is NOT proof that a
  person received or read the message; the system never claims otherwise.
* 429 responses honour `parameters.retry_after`; 5xx/network errors back off exponentially;
  4xx (except 429) are permanent and marked failed after one retry.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

import httpx
import pandas as pd

from ..signals.store import Store
from ..timeutil import iso, utcnow

API = "https://api.telegram.org"


def redact(text: str, token: str | None) -> str:
    if token:
        text = text.replace(token, "<redacted>")
    return re.sub(r"bot\d+:[A-Za-z0-9_-]{20,}", "bot<redacted>", text)


@dataclass
class SendResult:
    ok: bool
    message_id: int | None = None
    retry_after: float | None = None
    permanent: bool = False
    error: str = ""


class TelegramClient:
    def __init__(self, token: str, base_url: str = API, timeout: float = 15.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._token = token
        self.base = f"{base_url.rstrip('/')}/bot{token}"
        self.http = httpx.AsyncClient(timeout=timeout, transport=transport)

    async def call(self, method: str, **params) -> dict:
        r = await self.http.post(f"{self.base}/{method}", json=params)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error_code": r.status_code, "description": r.text[:200]}

    async def send(self, chat_id: str | int, text: str, silent: bool = False) -> SendResult:
        try:
            j = await self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                                disable_notification=silent, link_preview_options={"is_disabled": True})
        except httpx.HTTPError as ex:
            return SendResult(False, error=redact(f"network: {ex!r}", self._token))
        if j.get("ok"):
            return SendResult(True, message_id=j["result"]["message_id"])
        code = j.get("error_code", 0)
        desc = redact(str(j.get("description", "")), self._token)
        if code == 429:
            return SendResult(False, retry_after=float(j.get("parameters", {}).get("retry_after", 5)), error=desc)
        return SendResult(False, permanent=400 <= code < 500, error=f"{code} {desc}")

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        try:
            j = await self.call("getUpdates", **params)
        except httpx.HTTPError:
            return []
        return j.get("result", []) if j.get("ok") else []

    async def close(self):
        await self.http.aclose()


class Outbox:
    """Drains the persistent outbox with a global rate limit. Safe across restarts: rows are
    created with a unique dedupe key and only ever move pending -> accepted|failed."""

    def __init__(self, store: Store, client: TelegramClient | None, chats: dict[str, str],
                 max_per_minute: int = 20, now=utcnow):
        self.store, self.client, self.chats = store, client, chats
        self.min_gap = 60.0 / max_per_minute
        self._last = 0.0
        self.now = now

    async def drain_once(self) -> int:
        sent = 0
        for row in self.store.due_outbox(iso(self.now())):
            chat = self.chats.get(row["channel"])
            if self.client is None or not chat:
                # Delivery disabled: keep the row pending (visible in /status), do not pretend.
                continue
            wait = self.min_gap - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            res = await self.client.send(chat, row["text"], silent=row["kind"] in ("ops", "report"))
            self._last = time.monotonic()
            now = pd.Timestamp(self.now())
            if res.ok:
                self.store.mark_sent(row["id"], res.message_id, iso(now))
                sent += 1
            elif res.retry_after is not None:
                self.store.mark_retry(row["id"], res.error, iso(now + pd.Timedelta(seconds=res.retry_after + 1)))
            else:
                give_up = res.permanent and row["attempts"] >= 1 or row["attempts"] >= 8
                backoff = min(600, 5 * 2 ** row["attempts"])
                self.store.mark_retry(row["id"], res.error, iso(now + pd.Timedelta(seconds=backoff)), give_up)
                if give_up:
                    self.store.incident(iso(now), "telegram_delivery_failed", f"outbox {row['id']}: {res.error}")
        return sent
