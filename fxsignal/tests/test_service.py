"""End-to-end: Service on replayed bars -> signals -> lifecycle -> outbox -> (mock) Telegram.
Includes a restart in the middle and Telegram rate limiting. No network is used."""
import asyncio
import json

import httpx
import numpy as np
import pandas as pd
import pytest

from fxsignal.data.resample import resample
from fxsignal.live.app import replay
from fxsignal.news.calendar import CalEvent, blackout, parse_ff_json
from fxsignal.signals.store import Store
from fxsignal.telegram.admin import Admin
from fxsignal.telegram.client import Outbox, TelegramClient, redact
from conftest import synthetic_m15
from test_lifecycle import m1_series

CFG = {
    "symbols": ["EURUSD"],
    "risk": {"risk_per_trade_pct": 0.5, "max_currency_exposure_pct": 5, "max_open_risk_pct": 10,
             "min_reward_risk_after_costs": 0.5, "losing_streak_pause": 99, "max_spread_multiple": 10},
    "strategies": [{"family": "random", "params": {"p_signal": 0.3, "hold_h": 6}, "status": "research"}],
    "news": {"fail_closed": False},
    "ops": {"heartbeat_file": "var/heartbeat.json"},
}


class FakeTelegram:
    def __init__(self, rate_limit_first=True):
        self.sent, self.calls = [], 0
        self.rate_limit_first = rate_limit_first

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        body = json.loads(request.content)
        if self.rate_limit_first and self.calls == 1:
            return httpx.Response(429, json={"ok": False, "error_code": 429, "description": "Too Many Requests",
                                             "parameters": {"retry_after": 0}})
        self.sent.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.sent)}})


def data():
    m1 = m1_series(days=140, seed=11)
    return m1


def run(coro):
    return asyncio.run(coro)


def test_end_to_end_with_restart(tmp_path):
    m1 = data()
    split = m1.index[len(m1) * 3 // 4]
    hist = resample(m1[m1.index < split], "H1")
    live = m1[m1.index >= split]
    db = tmp_path / "db.sqlite"
    fake = FakeTelegram()
    client = TelegramClient("123:ABCDEFGHIJKLMNOPQRSTUVWXYZ", "https://tg.invalid",
                            transport=httpx.MockTransport(fake.handler))
    store = Store(db)
    ob = Outbox(store, client, {"admin": "42", "broadcast": ""}, max_per_minute=10_000)
    t0 = live.index[0]
    run(replay(CFG, store, {"EURUSD": m1}, t0, 60 * 24 * 3, tmp_path, {"EURUSD": hist}, ob))
    n_sig_1 = store.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert n_sig_1 > 0, "replay produced no signals"
    # --- restart: a fresh Service/Store object on the same DB re-processes the last hour --------
    store.conn.close()
    store2 = Store(db)
    ob2 = Outbox(store2, client, {"admin": "42", "broadcast": ""}, max_per_minute=10_000)
    t1 = t0 + pd.Timedelta(days=3) - pd.Timedelta(hours=1)  # overlap: replays an hour already seen
    hist2 = resample(m1[m1.index < t1], "H1")
    svc = run(replay(CFG, store2, {"EURUSD": m1}, t1, 60 * 24 * 2, tmp_path, {"EURUSD": hist2}, ob2))
    keys = [r[0] for r in store2.conn.execute("SELECT dedupe_key FROM outbox")]
    assert len(keys) == len(set(keys))
    texts = [m["text"] for m in fake.sent]
    assert len(texts) == len(set(texts)), "a message was delivered twice"
    # every signal: created + published, and lifecycle events only after creation
    for (sid,) in store2.conn.execute("SELECT id FROM signals"):
        ev = store2.events(sid)
        assert ev[0]["kind"] == "created" and ev[1]["kind"] == "published"
        kinds = [e["kind"] for e in ev]
        assert kinds.count("closed") <= 1 and kinds.count("triggered") <= 1
    # rate limit was honoured (first call 429, then retried) and acceptance recorded
    assert fake.calls >= len(fake.sent) + 1
    assert store2.outbox_stats().get("accepted", 0) == len(fake.sent)
    # research output is labelled and routed to admin only
    assert all(m["chat_id"] == "42" for m in fake.sent)
    assert any("RESEARCH ONLY" in m["text"] for m in fake.sent)
    assert all("[REPLAY]" in m["text"] for m in fake.sent)
    # immutability is enforced by the database
    sid = store2.conn.execute("SELECT id FROM signals LIMIT 1").fetchone()[0]
    with pytest.raises(Exception):
        store2.conn.execute("UPDATE signals SET stop=0 WHERE id=?", (sid,))
    with pytest.raises(Exception):
        store2.conn.execute("DELETE FROM events WHERE signal_id=?", (sid,))
    # heartbeat written atomically
    hb = json.loads((tmp_path / "var" / "heartbeat.json").read_text())
    assert hb["mode"] == "REPLAY" and "EURUSD" in hb["symbols"]
    # admin: unauthorised users get nothing; pause leaves tracking alone
    adm = Admin(svc, {7})
    assert adm.handle(8, "/status") is None
    assert "still tracked" in adm.handle(7, "/pause testing")
    assert "PAUSED" in adm.handle(7, "/status")
    assert "No trade" in adm.handle(7, "/size EURUSD 300 USD 0.5 1.1000 1.0950")
    assert "lots" in adm.handle(7, "/size EURUSD 10000 USD 0.5 1.1000 1.0950")
    assert "hard cap" in adm.handle(7, "/size EURUSD 10000 USD 5 1.1000 1.0950")


def test_paused_service_creates_no_new_signals(tmp_path):
    m1 = data()
    split = m1.index[len(m1) * 3 // 4]
    store = Store(tmp_path / "db.sqlite")
    store.kv_set("paused", True, "2020-01-01T00:00:00+00:00")
    run(replay(CFG, store, {"EURUSD": m1}, split, 60 * 24 * 2, tmp_path,
               {"EURUSD": resample(m1[m1.index < split], "H1")}))
    assert store.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0
    assert any("paused" in k for k in store.kv_get(next(iter(
        [r[0] for r in store.conn.execute("SELECT key FROM kv WHERE key LIKE 'abstain:%'")])), {}))


def test_calendar_fail_closed_blocks_signals(tmp_path):
    m1 = data()
    split = m1.index[len(m1) * 3 // 4]
    cfg = dict(CFG, news={"fail_closed": True})
    store = Store(tmp_path / "db.sqlite")
    run(replay(cfg, store, {"EURUSD": m1}, split, 60 * 24 * 2, tmp_path,
               {"EURUSD": resample(m1[m1.index < split], "H1")}))
    assert store.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0


def test_blackout_window_and_parsing():
    items = [{"title": "Non-Farm Employment Change", "country": "USD", "date": "2024-03-08T08:30:00-05:00",
              "impact": "High", "forecast": "200K", "previous": "229K"},
             {"title": "<script>bad</script>", "country": "XXX", "date": "2024-03-08T08:30:00-05:00", "impact": "High"},
             {"title": "no tz", "country": "EUR", "date": "2024-03-08T08:30:00", "impact": "High"}]
    ev = parse_ff_json(items)
    assert len(ev) == 1 and ev[0].scheduled_at == "2024-03-08T13:30:00+00:00" and ev[0].tag == "employment"
    now = pd.Timestamp("2024-03-08 13:00", tz="UTC")
    b = blackout(("EUR", "USD"), now, ev, now)
    assert b.blocked  # NFP is "major": 30 + 30 min before
    assert not blackout(("EUR", "GBP"), now, ev, now).blocked
    assert blackout(("EUR", "GBP"), now, ev, None).blocked  # no calendar -> fail closed
    assert not blackout(("EUR", "USD"), now - pd.Timedelta(hours=3), ev, now).blocked


def test_token_redaction():
    t = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
    assert t not in redact(f"error calling https://api.telegram.org/bot{t}/sendMessage", t)
    assert "<redacted>" in redact(f"bot{t}", None)
