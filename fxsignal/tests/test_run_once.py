"""Scheduled one-shot mode (GitHub Actions): state carried between runs in the SQLite file."""
import asyncio
import json

import httpx
import pandas as pd

from fxsignal.data.resample import resample
from fxsignal.live.app import run_once
from fxsignal.live.feeds import TwelveDataFeed
from fxsignal.telegram.client import TelegramClient
from conftest import synthetic_m15

CFG = {
    "mode": "research_paper",
    "symbols": ["EURUSD"],
    "risk": {"risk_per_trade_pct": 0.5, "max_currency_exposure_pct": 5, "max_open_risk_pct": 10,
             "min_reward_risk_after_costs": 0.5, "losing_streak_pause": 99, "max_spread_multiple": 10},
    "strategies": [{"family": "random", "params": {"p_signal": 0.5, "hold_h": 4}, "status": "research"}],
    "news": {"fail_closed": False},
    "storage": {"db_path": "var/fx.sqlite"},
    "ops": {},
}


class World:
    def __init__(self):
        self.m15 = synthetic_m15(n_days=120, seed=21)
        self.h1 = resample(self.m15, "H1")
        self.clock = self.h1.index[len(self.h1) * 3 // 4] + pd.Timedelta(minutes=7)
        self.sent, self.updates, self.td_calls = [], [], 0

    def twelvedata(self, req):
        self.td_calls += 1
        q = dict(req.url.params)
        if req.url.path == "/price":
            p = self.m15[self.m15.index + pd.Timedelta(minutes=15) <= self.clock]["close"].iloc[-1]
            return httpx.Response(200, json={"price": str(p)})
        upto = self.h1[self.h1.index <= self.clock].tail(int(q["outputsize"]))
        vals = [{"datetime": t.strftime("%Y-%m-%d %H:%M:%S"), "open": r.open, "high": r.high, "low": r.low,
                 "close": r.close} for t, r in upto.iterrows()]
        return httpx.Response(200, json={"values": vals, "status": "ok"})

    def telegram(self, req):
        body = json.loads(req.content)
        if req.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"username": "test_bot"}})
        if req.url.path.endswith("/getUpdates"):
            off = body.get("offset") or 0
            return httpx.Response(200, json={"ok": True, "result": [u for u in self.updates if u["update_id"] >= off]})
        self.sent.append(body)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.sent)}})


def one(w, tmp_path):
    feed = TwelveDataFeed("k", transport=httpx.MockTransport(w.twelvedata), clock=lambda: w.clock, per_minute=10**6)
    tg = TelegramClient("1:x", "https://tg.invalid", transport=httpx.MockTransport(w.telegram))
    return asyncio.run(run_once(CFG, tmp_path, feed=feed, tg=tg, chats={}, admins=set(), history_bars=1500))


def test_hourly_runs_carry_state(tmp_path):
    w = World()
    w.updates.append({"update_id": 10, "message": {"text": "/start", "from": {"id": 555}, "chat": {"id": 555, "type": "private"}}})
    info = one(w, tmp_path)
    assert info["new_bars"]["EURUSD"] == 1
    assert info["telegram"] == "ok as @test_bot" and info["telegram_messages_received"] == 1 and info["admin_known"]
    assert any("You are now the admin" in m["text"] for m in w.sent)
    # a stranger later cannot take over or read anything
    w.updates.append({"update_id": 11, "message": {"text": "/status", "from": {"id": 999}, "chat": {"id": 999, "type": "private"}}})
    w.updates.append({"update_id": 12, "message": {"text": "/status", "from": {"id": 555}, "chat": {"id": 555, "type": "private"}}})
    news = []
    for h in range(24 * 5):
        w.clock += pd.Timedelta(hours=1)
        info = one(w, tmp_path)
        news.append(info["new_bars"]["EURUSD"])
    assert all(m["chat_id"] in (555, "555") for m in w.sent)  # nothing ever went to the stranger
    assert sum("<b>Status</b>" in m["text"] for m in w.sent) == 1  # /status answered once, not every run
    texts = [m["text"] for m in w.sent]
    assert len(texts) == len(set(texts))  # no duplicates across runs
    kinds = " ".join(texts)
    assert "RESEARCH ONLY" in kinds and "Daily report" in kinds and ("Closed" in kinds or "Do not chase" in kinds)
    # a skipped hour is caught up next run
    w.clock += pd.Timedelta(hours=3)
    info = one(w, tmp_path)
    assert info["new_bars"]["EURUSD"] in (0, 3)  # 0 only if the gap fell on the weekend
    assert set(news) <= {0, 1}
