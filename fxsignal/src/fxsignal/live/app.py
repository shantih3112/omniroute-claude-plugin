"""Process entry points: live/paper service with asyncio tasks, and fast replay runs.

Tasks in `serve()`:
  scanner   – Service.step() every poll interval
  outbox    – drains the Telegram outbox (rate limited, retries, dedupe)
  admin     – long-polls getUpdates for admin commands (authorised IDs only)
  calendar  – refreshes the economic calendar hourly (fail-closed if it goes stale)
  health    – tiny HTTP endpoint on 127.0.0.1 for the watchdog / Docker healthcheck
A failure in one task is logged as an incident and that task restarts after a delay; it does
not take down the others. The process itself is restarted by systemd/Docker if it exits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal as _signal
from pathlib import Path

import httpx
import pandas as pd
import yaml

from ..news import calendar as cal
from ..signals.store import Store
from ..telegram.admin import Admin
from ..telegram.client import Outbox, TelegramClient, redact
from ..timeutil import iso
from .feeds import OandaFeed, ReplayFeed
from .service import Service

log = logging.getLogger("fxsignal")


def load_config(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def telegram_from_env() -> tuple[TelegramClient | None, dict[str, str], set[int]]:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chats = {"admin": os.environ.get("TELEGRAM_ADMIN_CHAT_ID", ""),
             "broadcast": os.environ.get("TELEGRAM_CHANNEL_ID", "")}
    admins = {int(x) for x in os.environ.get("TELEGRAM_ADMIN_IDS", "").replace(" ", "").split(",") if x}
    base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    return (TelegramClient(tok, base) if tok else None), chats, admins


async def _guard(name: str, store: Store, coro_fn, every: float, stop: asyncio.Event):
    while not stop.is_set():
        try:
            await coro_fn()
        except Exception as ex:  # keep other tasks alive; record and back off
            tok = os.environ.get("TELEGRAM_BOT_TOKEN")
            try:
                store.incident(iso(pd.Timestamp.now(tz="UTC")), f"task_error:{name}", redact(repr(ex), tok)[:500])
            except Exception:  # the database itself may be the failing component
                pass
            log.error("task %s failed: %s", name, redact(repr(ex), tok)[:500])
            await asyncio.sleep(min(60, every * 3))
        try:
            await asyncio.wait_for(stop.wait(), timeout=every)
        except asyncio.TimeoutError:
            pass


async def serve(config_path: str, base_dir: Path) -> None:
    cfg = load_config(config_path)
    store = Store(base_dir / cfg["storage"]["db_path"])
    feed = OandaFeed()
    svc = Service(cfg, store, feed, label="LIVE-PAPER" if cfg.get("mode") != "research_paper" else "RESEARCH-PAPER",
                  base_dir=base_dir)
    for s in svc.symbols:
        svc.seed_history(s, await feed.history_h1(s, 5000))
    svc.update_correlations()
    info = svc.restore()
    log.info("restored %s", info)
    tg, chats, admins = telegram_from_env()
    outbox = Outbox(store, tg, chats, cfg.get("telegram", {}).get("max_messages_per_minute", 20))
    admin = Admin(svc, admins)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (_signal.SIGTERM, _signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    http = httpx.AsyncClient(timeout=20)
    offset = {"v": store.kv_get("tg_offset")}

    async def admin_poll():
        if tg is None:
            await asyncio.sleep(5)
            return
        for u in await tg.get_updates(offset["v"]):
            offset["v"] = u["update_id"] + 1
            store.kv_set("tg_offset", offset["v"], iso(pd.Timestamp.now(tz="UTC")))
            m = u.get("message") or {}
            reply = admin.handle((m.get("from") or {}).get("id"), m.get("text", ""))
            if reply and m.get("chat", {}).get("type") == "private":
                await tg.send(m["chat"]["id"], reply)

    async def refresh_calendar():
        evs = await cal.fetch_ff(http)
        svc.set_calendar(evs, pd.Timestamp.now(tz="UTC"))

    async def daily_corr():
        svc.update_correlations()

    health_port = cfg.get("ops", {}).get("health_port", 8087)

    async def handle_health(reader, writer):
        await reader.read(1024)
        h = svc.health()
        ok = all(v["status"] in ("ok", "market_closed") for v in h["symbols"].values())
        body = json.dumps(h, default=str).encode()
        writer.write(b"HTTP/1.1 " + (b"200 OK" if ok else b"503 Degraded") +
                     b"\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() +
                     b"\r\nConnection: close\r\n\r\n" + body)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle_health, "127.0.0.1", health_port)
    poll = cfg.get("feed", {}).get("poll_seconds", 10)
    tasks = [
        asyncio.create_task(_guard("scanner", store, svc.step, poll, stop)),
        asyncio.create_task(_guard("outbox", store, outbox.drain_once, 2, stop)),
        asyncio.create_task(_guard("admin", store, admin_poll, 1, stop)),
        asyncio.create_task(_guard("calendar", store, refresh_calendar, 3600, stop)),
        asyncio.create_task(_guard("correlations", store, daily_corr, 6 * 3600, stop)),
    ]
    await stop.wait()
    for t in tasks:
        t.cancel()
    server.close()
    await http.aclose()
    if tg:
        await tg.close()
    await feed.close()
    store.incident(iso(pd.Timestamp.now(tz="UTC")), "shutdown", "clean shutdown")


async def replay(cfg: dict, store: Store, m1: dict[str, pd.DataFrame], start: pd.Timestamp, minutes: int,
                 base_dir: Path, h1_history: dict[str, pd.DataFrame] | None = None, outbox: Outbox | None = None,
                 calendar: list | None = None) -> Service:
    """Drive the real Service on historical M1 data with a simulated clock (no network)."""
    feed = ReplayFeed(m1, start)
    svc = Service(cfg, store, feed, label="REPLAY", base_dir=base_dir)
    for s in svc.symbols:
        if h1_history and s in h1_history:
            svc.seed_history(s, h1_history[s])
    svc.update_correlations()
    svc.restore()
    if calendar is not None:
        svc.set_calendar(calendar, start)
    for _ in range(minutes):
        feed.advance(1)
        await svc.step()
        if outbox is not None:
            await outbox.drain_once()
    return svc
