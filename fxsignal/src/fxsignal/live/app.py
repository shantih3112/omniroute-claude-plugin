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
from .feeds import OandaFeed, ReplayFeed, TwelveDataFeed
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


def make_feed(cfg: dict):
    """Pick the price feed from config (`feed.provider`), falling back to whatever key exists."""
    prov = cfg.get("feed", {}).get("provider", "auto")
    if prov == "auto":
        prov = "oanda" if os.environ.get("OANDA_API_TOKEN") else "twelvedata"
    if prov == "oanda":
        return OandaFeed()
    if prov == "twelvedata":
        return TwelveDataFeed()
    raise ValueError(f"unknown feed provider {prov!r}")


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
    feed = make_feed(cfg)
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
        svc.prune(30)

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


class BatchFeed:
    """Hands the service the bars that completed since the previous run, then nothing.
    Quotes and the clock come from the real feed underneath."""

    def __init__(self, inner):
        self.inner = inner
        self.pending: dict[str, list] = {}
        self.bar_minutes = getattr(inner, "bar_minutes", 60)
        self.name = f"batch:{getattr(inner, 'name', '?')}"

    def now(self):
        return self.inner.now()

    async def poll(self, symbol):
        from .feeds import FeedBatch
        bars, self.pending[symbol] = self.pending.get(symbol, []), []
        return FeedBatch(symbol, bars, self.now())

    async def quote(self, symbol):
        return await self.inner.quote(symbol)


async def run_once(cfg: dict, base_dir: Path, feed=None, tg: TelegramClient | None = None,
                   chats: dict | None = None, admins: set[int] | None = None, http=None,
                   history_bars: int = 1500) -> dict:
    """One scheduled cycle (e.g. hourly GitHub Actions run) with state kept in the SQLite file.

    Processes every hourly bar that completed since the last run (gaps are caught up), tracks
    open paper signals, generates and publishes signals for the latest bar only (older bars are
    rejected by the processing-lag rule), refreshes the calendar, answers admin commands that
    arrived since the last run, sends the daily report when due, and drains the outbox.
    """
    store = Store(base_dir / cfg["storage"]["db_path"])
    feed = feed or make_feed(cfg)
    bf = BatchFeed(feed)
    label = "RESEARCH-PAPER" if cfg.get("mode") == "research_paper" else "LIVE-PAPER"
    svc = Service(cfg, store, bf, label=label, base_dir=base_dir)
    # a scheduled job can start late; signals more than this after the bar close are not published
    svc.max_lag = pd.Timedelta(minutes=cfg.get("feed", {}).get("batch_max_lag_min", 45))
    info = {"new_bars": {}}
    restored = svc.restore()
    for sym in svc.symbols:
        hist = await feed.history_h1(sym, history_bars)
        last = svc.st[sym].last_bar_t
        if last is None:  # first run: everything is history except the newest completed bar
            seed, new = hist.iloc[:-1], hist.iloc[-1:]
        else:
            seed, new = hist[hist.index <= last], hist[hist.index > last]
        svc.seed_history(sym, seed)
        from ..signals.lifecycle import Bar
        bf.pending[sym] = [Bar(t, float(r.open), float(r.high), float(r.low), float(r.close), None)
                           for t, r in new.iterrows()]
        info["new_bars"][sym] = len(new)
    svc.update_correlations()
    if http is not None:
        try:
            svc.set_calendar(await cal.fetch_ff(http), pd.Timestamp(feed.now()))
        except Exception as ex:
            store.incident(iso(feed.now()), "calendar_error", f"{type(ex).__name__}: {str(ex)[:200]}")
    info["cycle"] = await svc.step()
    svc.prune(30)
    # admin commands received since the last run
    chats = dict(chats or {})
    admins = set(admins or set())
    if tg is not None:
        offset = store.kv_get("tg_offset")
        updates = await tg.get_updates(offset, timeout=0)
        if not admins:
            saved = store.kv_get("auto_admin_id")
            if saved:
                admins = {int(saved)}
            else:
                # no admin configured: the FIRST person who messaged the bot privately becomes admin
                first = next((u["message"] for u in updates if u.get("message", {}).get("chat", {}).get("type") == "private"), None)
                if first:
                    admins = {int(first["from"]["id"])}
                    store.kv_set("auto_admin_id", first["from"]["id"], iso(feed.now()))
                    store.incident(iso(feed.now()), "admin_auto_set", str(first["from"]["id"]))
                    await tg.send(first["chat"]["id"],
                                  "You are now the admin of this fxsignal bot (first person to message it). "
                                  "If that is wrong, set the TELEGRAM_ADMIN_ID secret. Send /help for commands.")
        if not chats.get("admin") and admins:
            chats["admin"] = str(next(iter(admins)))
        admin = Admin(svc, admins)
        for u in updates:
            store.kv_set("tg_offset", u["update_id"] + 1, iso(feed.now()))
            m = u.get("message") or {}
            reply = admin.handle((m.get("from") or {}).get("id"), m.get("text", ""))
            if reply and m.get("chat", {}).get("type") == "private":
                await tg.send(m["chat"]["id"], reply)
        info["commands"] = len(updates)
    sent = await Outbox(store, tg, chats, 20, now=lambda: feed.now()).drain_once() if tg else 0
    info.update(sent=sent, outbox=store.outbox_stats(), restored=restored,
                symbols={s: v.status for s, v in svc.st.items()})
    store.conn.close()
    return info
