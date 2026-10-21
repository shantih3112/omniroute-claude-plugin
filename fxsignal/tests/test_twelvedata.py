"""Twelve Data hourly feed against a mocked API, and the service running on hourly bars."""
import asyncio

import httpx
import pandas as pd
import pytest

from fxsignal.data.resample import resample
from fxsignal.live.app import replay
from fxsignal.live.feeds import FeedError, RateLimiter, ReplayFeed, TwelveDataFeed
from fxsignal.live.service import Service
from fxsignal.signals.store import Store
from fxsignal.timeutil import last_market_open
from conftest import synthetic_m15
from test_service import CFG


def api(h1: pd.DataFrame, clock, calls: list):
    def handler(req: httpx.Request):
        q = dict(req.url.params)
        calls.append(q)
        assert q["symbol"] == "EUR/USD" and q["interval"] == "1h" and q["timezone"] == "UTC"
        if q["apikey"] != "k":
            return httpx.Response(401, json={"code": 401, "message": "bad key", "status": "error"})
        # vendor returns candles up to and INCLUDING the one still forming
        upto = h1[h1.index <= clock["t"]].tail(int(q["outputsize"]))
        vals = [{"datetime": t.strftime("%Y-%m-%d %H:%M:%S"), "open": str(r.open), "high": str(r.high),
                 "low": str(r.low), "close": str(r.close)} for t, r in upto.iterrows()]
        return httpx.Response(200, json={"meta": {"symbol": q["symbol"]}, "values": vals, "status": "ok"})
    return handler


@pytest.fixture
def h1():
    return resample(synthetic_m15(n_days=60), "H1")


def test_parses_and_drops_forming_candle(h1):
    clock = {"t": h1.index[200] + pd.Timedelta(minutes=30)}  # mid-way through bar 200
    calls = []
    f = TwelveDataFeed("k", transport=httpx.MockTransport(api(h1, clock, calls)), clock=lambda: clock["t"])
    hist = asyncio.run(f.history_h1("EURUSD", 50))
    assert hist.index[-1] == h1.index[199]  # bar 200 is still forming -> excluded
    assert hist["close"].iloc[-1] == pytest.approx(h1["close"].iloc[199])
    # nothing new until the next hour has closed
    assert asyncio.run(f.poll("EURUSD")).bars == []
    clock["t"] = h1.index[201] + pd.Timedelta(minutes=2)
    b = asyncio.run(f.poll("EURUSD")).bars
    assert [x.t for x in b] == [h1.index[200]]


def test_quote_endpoint(h1):
    def handler(req):
        assert req.url.path == "/price" and req.url.params["symbol"] == "GBP/USD"
        return httpx.Response(200, json={"price": "1.33251"})
    t = pd.Timestamp("2026-10-20 10:02", tz="UTC")
    f = TwelveDataFeed("k", transport=httpx.MockTransport(handler), clock=lambda: t)
    assert asyncio.run(f.quote("GBPUSD")) == (t, 1.33251)


def test_error_and_missing_key(h1):
    clock = {"t": h1.index[100]}
    f = TwelveDataFeed("wrong", transport=httpx.MockTransport(api(h1, clock, [])), clock=lambda: clock["t"])
    with pytest.raises(FeedError, match="401"):
        asyncio.run(f.poll("EURUSD"))
    with pytest.raises(FeedError):
        TwelveDataFeed("", transport=None)


def test_rate_limiter_minute_and_day():
    t = {"v": pd.Timestamp("2026-10-20 10:00", tz="UTC")}
    rl = RateLimiter(7, 10, lambda: t["v"])
    for _ in range(7):
        assert rl.allow()
        rl.take()
    assert not rl.allow()
    t["v"] += pd.Timedelta(seconds=61)
    for _ in range(3):
        assert rl.allow()
        rl.take()
    assert not rl.allow()  # daily budget
    t["v"] += pd.Timedelta(days=1)
    assert rl.allow()


def test_budget_for_eleven_pairs_hourly():
    # 11 symbols x 24 polls = 264/day, far below the 780 budget; startup history adds 11
    assert 11 * 24 + 11 < 780


def test_service_on_hourly_bars(tmp_path, h1):
    m15 = synthetic_m15(n_days=140, seed=11)
    hh = resample(m15, "H1")
    split = hh.index[len(hh) * 3 // 4]
    store = Store(tmp_path / "db.sqlite")
    cfg = dict(CFG, strategies=[{"family": "random", "params": {"p_signal": 0.3, "hold_h": 6}, "status": "research"}])
    class QuotingReplay(ReplayFeed):
        """Hourly replay plus a 'quote' = the 15-minute close at/just before the clock."""
        async def quote(self, sym):
            q = m15[m15.index + pd.Timedelta(minutes=15) <= self.clock]
            return self.clock, float(q["close"].iloc[-1])
    feed = QuotingReplay({"EURUSD": hh}, split, bar_minutes=60)
    svc = Service(cfg, store, feed, label="REPLAY", base_dir=tmp_path)
    svc.seed_history("EURUSD", hh[hh.index < split])
    for _ in range(24 * 6 * 6):  # 6 days in 10-minute steps
        feed.advance(10)
        asyncio.run(svc.step())
        assert svc.st["EURUSD"].status in ("ok", "market_closed", "starting"), svc.st["EURUSD"].status_reason
    n = store.conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    kinds = {r[0] for r in store.conn.execute("SELECT kind FROM events")}
    assert n > 0 and "closed" in kinds
    # paper entries never happen on a bar that opened before the signal was published
    trig = 0
    for (sid, created) in store.conn.execute("SELECT id, created_at FROM signals"):
        for e in store.events(sid):
            if e["kind"] == "triggered":
                trig += 1
                assert pd.Timestamp(e["ts"]) > pd.Timestamp(created)
                assert '"source": "quote at publication"' in e["detail"]
    assert trig > 0


def test_last_market_open():
    assert last_market_open(pd.Timestamp("2026-10-21 12:00", tz="UTC")) == pd.Timestamp("2026-10-18 21:00", tz="UTC")
    assert last_market_open(pd.Timestamp("2026-12-06 23:00", tz="UTC")) == pd.Timestamp("2026-12-06 22:00", tz="UTC")
