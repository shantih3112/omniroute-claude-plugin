"""Failure behaviour: each failure pauses the right capability and keeps the rest running."""
import asyncio
import json
import os
import sqlite3
import time

import httpx
import pandas as pd
import pytest

from fxsignal.data.resample import resample
from fxsignal.live.feeds import ReplayFeed
from fxsignal.live.service import Service
from fxsignal.ops.watchdog import check
from fxsignal.signals.store import Store
from fxsignal.telegram.client import Outbox, TelegramClient
from test_lifecycle import m1_series
from test_service import CFG


def make(tmp_path, symbols=("EURUSD", "GBPUSD"), cfg_extra=None):
    m1 = m1_series(days=60, seed=5)
    start = m1.index[len(m1) * 3 // 4]
    data = {s: m1 for s in symbols}
    cfg = dict(CFG, symbols=list(symbols), **(cfg_extra or {}))
    store = Store(tmp_path / "db.sqlite")
    feed = ReplayFeed(data, start)
    svc = Service(cfg, store, feed, label="REPLAY", base_dir=tmp_path)
    for s in symbols:
        svc.seed_history(s, resample(m1[m1.index < start], "H1"))
    return svc, feed, store


class BrokenFeed:
    """Wraps a feed; one symbol raises (simulated disconnect)."""
    def __init__(self, inner, bad):
        self.inner, self.bad = inner, bad

    def now(self):
        return self.inner.now()

    async def poll(self, sym):
        if sym == self.bad:
            raise ConnectionError("simulated disconnect")
        return await self.inner.poll(sym)


def test_feed_disconnect_isolated_to_symbol(tmp_path):
    svc, feed, store = make(tmp_path)
    svc.feed = BrokenFeed(feed, "GBPUSD")
    for _ in range(90):
        feed.advance(1)
        asyncio.run(svc.step())
    assert svc.st["GBPUSD"].status == "feed_error"
    assert svc.st["EURUSD"].status in ("ok", "market_closed")
    assert any(i["kind"] == "feed_error" for i in store.incidents_since("2000"))
    # only one incident per outage, not one per poll
    assert sum(i["kind"] == "feed_error" for i in store.incidents_since("2000")) == 1


def test_stale_data_blocks_signals(tmp_path):
    svc, feed, store = make(tmp_path, ("EURUSD",))
    for _ in range(30):
        feed.advance(1)
        asyncio.run(svc.step())
    # feed goes silent while the market is open: the clock moves, no bars arrive
    svc.feed = type("Silent", (), {"now": lambda self: feed.now(), "poll": None})()

    async def silent(sym):
        from fxsignal.live.feeds import FeedBatch
        return FeedBatch(sym, [])
    svc.feed.poll = silent
    for _ in range(5):
        feed.advance(1)
        asyncio.run(svc.step())
    assert svc.st["EURUSD"].status == "stale"  # fixture starts on a Wednesday evening: market open
    row = type("R", (), dict(time=feed.now(), side=1, entry_ref=1.1, stop=1.09, target=1.12, entry_type="market",
                             max_hold_min=60, expiry_min=30, regime="", note=""))()
    ok, reasons, _ = svc._policy("EURUSD", "random", None, "research", row, feed.now())
    assert not ok and any("data not OK" in r for r in reasons)


def test_telegram_down_keeps_messages_and_backs_off(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    now = pd.Timestamp("2024-03-04 10:00", tz="UTC")
    store.enqueue("k1", "admin", "signal", "hello", now.isoformat())

    def down(request):
        raise httpx.ConnectError("unreachable")
    client = TelegramClient("1:abc", "https://tg.invalid", transport=httpx.MockTransport(down))
    clock = {"t": now}
    ob = Outbox(store, client, {"admin": "42"}, max_per_minute=10**6, now=lambda: clock["t"])
    for k in range(12):
        asyncio.run(ob.drain_once())
        clock["t"] = clock["t"] + pd.Timedelta(minutes=15)
    row = store.conn.execute("SELECT * FROM outbox WHERE dedupe_key='k1'").fetchone()
    assert row["status"] == "failed" and row["attempts"] >= 8
    assert any(i["kind"] == "telegram_delivery_failed" for i in store.incidents_since("2000"))
    # nothing was marked as delivered
    assert store.outbox_stats().get("accepted", 0) == 0


def test_delivery_disabled_does_not_pretend(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.enqueue("k1", "admin", "signal", "hello", "2024-03-04T10:00:00+00:00")
    ob = Outbox(store, None, {"admin": ""}, now=lambda: pd.Timestamp("2024-03-05", tz="UTC"))
    asyncio.run(ob.drain_once())
    assert store.outbox_stats() == {"pending": 1}


def test_database_failure_stops_cycle_and_heartbeat_goes_stale(tmp_path):
    svc, feed, store = make(tmp_path, ("EURUSD",))
    feed.advance(5)
    asyncio.run(svc.step())
    hb = tmp_path / "var" / "heartbeat.json"
    t_ok = hb.stat().st_mtime

    def boom(*a, **k):
        raise sqlite3.OperationalError("disk I/O error")
    store.upsert_bars = boom
    feed.advance(5)
    time.sleep(0.01)
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(svc.step())
    assert hb.stat().st_mtime == t_ok  # no heartbeat for a failed cycle -> watchdog will see it age
    os.utime(hb, (t_ok - 600, t_ok - 600))
    ok, why = check(hb, 120, None)
    assert not ok and "heartbeat" in why


def test_watchdog_flags_degraded_data(tmp_path):
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({"symbols": {"EURUSD": {"status": "stale"}}}))
    ok, why = check(hb, 120, None)
    assert not ok and "EURUSD:stale" in why
    hb.write_text(json.dumps({"symbols": {"EURUSD": {"status": "ok"}}}))
    assert check(hb, 120, None)[0]
