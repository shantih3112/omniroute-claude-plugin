"""Price feeds for the live/paper service. All return COMPLETED one-minute bars (BID OHLC, UTC
open time) plus the measured close spread when the source provides ask prices.

* ReplayFeed : replays real historical M1 data on a simulated clock (demo, tests, soak runs).
               Everything it produces is labelled REPLAY by the service.
* OandaFeed  : OANDA v20 REST `GET /v3/instruments/{instrument}/candles?price=BA&granularity=M1`,
               using only candles with `complete: true`. Needs OANDA_API_TOKEN (a free practice
               account works) and OANDA_HOST (practice: https://api-fxpractice.oanda.com).
               NOT exercised against the real API from the build environment (host blocked);
               scripts/feed_selftest.py checks it once credentials exist.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import pandas as pd

from ..signals.lifecycle import Bar


class FeedError(RuntimeError):
    pass


@dataclass
class FeedBatch:
    symbol: str
    bars: list[Bar]
    source_time: pd.Timestamp | None = None   # provider's clock if known


class ReplayFeed:
    def __init__(self, m1: dict[str, pd.DataFrame], start: pd.Timestamp, spread_model=None, bar_minutes: int = 1):
        self.m1 = {k: v.sort_index() for k, v in m1.items()}
        self.clock = pd.Timestamp(start)
        self._cursor = {k: int(v.index.searchsorted(self.clock)) for k, v in self.m1.items()}
        self.spread_model = spread_model
        self.name = "replay"
        self.bar_minutes = bar_minutes

    def now(self) -> pd.Timestamp:
        return self.clock

    def advance(self, minutes: int = 1) -> None:
        self.clock = self.clock + pd.Timedelta(minutes=minutes)

    async def poll(self, symbol: str) -> FeedBatch:
        df = self.m1[symbol]
        i = self._cursor[symbol]
        out = []
        # a bar is complete once the clock has passed its close
        while i < len(df) and df.index[i] + pd.Timedelta(minutes=self.bar_minutes) <= self.clock:
            r = df.iloc[i]
            sp = self.spread_model(symbol, df.index[i]) if self.spread_model else None
            out.append(Bar(df.index[i], float(r.open), float(r.high), float(r.low), float(r.close), sp))
            i += 1
        self._cursor[symbol] = i
        return FeedBatch(symbol, out, self.clock)

    def history(self, symbol: str, before: pd.Timestamp) -> pd.DataFrame:
        df = self.m1[symbol]
        return df[df.index + pd.Timedelta(minutes=self.bar_minutes) <= before]


def oanda_instrument(symbol: str) -> str:
    return f"{symbol[:3]}_{symbol[3:]}"


class OandaFeed:
    def __init__(self, token: str | None = None, host: str | None = None, timeout: float = 15.0):
        self.token = token or os.environ.get("OANDA_API_TOKEN", "")
        self.host = (host or os.environ.get("OANDA_HOST", "https://api-fxpractice.oanda.com")).rstrip("/")
        if not self.token:
            raise FeedError("OANDA_API_TOKEN is not set")
        self.http = httpx.AsyncClient(timeout=timeout, headers={"Authorization": f"Bearer {self.token}",
                                                                "Accept-Datetime-Format": "RFC3339"})
        self.last: dict[str, pd.Timestamp] = {}
        self.name = "oanda"
        self.bar_minutes = 1

    def now(self) -> pd.Timestamp:
        return pd.Timestamp.now(tz="UTC")

    async def candles(self, symbol: str, granularity: str = "M1", count: int | None = None,
                      frm: pd.Timestamp | None = None) -> list[dict]:
        params = {"price": "BA", "granularity": granularity}
        if frm is not None:
            params["from"] = frm.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
            params["count"] = 5000
        else:
            params["count"] = count or 500
        r = await self.http.get(f"{self.host}/v3/instruments/{oanda_instrument(symbol)}/candles", params=params)
        if r.status_code != 200:
            raise FeedError(f"OANDA {r.status_code}: {r.text[:200]}")
        return r.json().get("candles", [])

    @staticmethod
    def to_bar(c: dict) -> Bar | None:
        if not c.get("complete"):
            return None
        b, a = c.get("bid"), c.get("ask")
        if not b:
            return None
        t = pd.Timestamp(c["time"]).tz_convert("UTC")
        sp = float(a["c"]) - float(b["c"]) if a else None
        return Bar(t, float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"]), sp)

    async def poll(self, symbol: str) -> FeedBatch:
        frm = self.last.get(symbol)
        # resumes from the last processed bar (after a restart this pages forward up to 5000 bars)
        cs = await self.candles(symbol, frm=frm + pd.Timedelta(minutes=1) if frm is not None else None, count=10)
        bars = [b for b in (self.to_bar(c) for c in cs) if b is not None]
        if frm is not None:
            bars = [b for b in bars if b.t > frm]
        if bars:
            self.last[symbol] = bars[-1].t
        return FeedBatch(symbol, bars, self.now())

    async def history_h1(self, symbol: str, count: int = 5000) -> pd.DataFrame:
        cs = await self.candles(symbol, "H1", count=count)
        rows = [self.to_bar(c) for c in cs]
        rows = [r for r in rows if r is not None]
        df = pd.DataFrame([(r.t, r.o, r.h, r.l, r.c) for r in rows], columns=["time", "open", "high", "low", "close"])
        return df.set_index("time").assign(tick_volume=0.0)

    async def close(self):
        await self.http.aclose()


class RateLimiter:
    """At most `per_minute` calls in any rolling 60 s window and `per_day` per UTC day."""

    def __init__(self, per_minute: int, per_day: int, clock=lambda: pd.Timestamp.now(tz="UTC")):
        self.per_minute, self.per_day, self.clock = per_minute, per_day, clock
        self.recent: list[pd.Timestamp] = []
        self.day, self.day_count = None, 0

    def allow(self) -> bool:
        now = self.clock()
        self.recent = [t for t in self.recent if now - t < pd.Timedelta(seconds=60)]
        if self.day != now.date():
            self.day, self.day_count = now.date(), 0
        return len(self.recent) < self.per_minute and self.day_count < self.per_day

    def take(self) -> None:
        self.recent.append(self.clock())
        self.day_count += 1


class TwelveDataFeed:
    """Twelve Data REST `GET /time_series` (https://api.twelvedata.com), free "Basic" plan.

    Free-plan limits as published by Twelve Data (8 credits/minute, 800/day; 1 credit per symbol
    per time_series call). One-minute polling of 11 pairs would need ~15,800 credits/day, so this
    feed works on HOURLY bars: each symbol is fetched once shortly after every hour closes
    (11 pairs x 24 = 264 credits/day), staggered to stay under 7 calls/minute.

    Limitations (shown in reports): one price series per pair (Twelve Data does not say whether
    it is bid or mid; no ask, so spreads are modelled); paper entries happen at the open of the
    first hourly bar after publication (about one hour later than a person could act), and
    stops/targets inside an hour are resolved with the conservative stop-first rule.
    The newest candle returned by the API may still be forming; it is never used.
    NOT tested against the real API from the build environment (host blocked);
    run `fxsignal feed-selftest` on the server.
    """

    BASE = "https://api.twelvedata.com"

    def __init__(self, api_key: str | None = None, interval_min: int = 60, per_minute: int = 7, per_day: int = 780,
                 timeout: float = 20.0, transport=None, clock=None, base_url: str | None = None):
        self.key = api_key or os.environ.get("TWELVEDATA_API_KEY", "")
        if not self.key:
            raise FeedError("TWELVEDATA_API_KEY is not set")
        if interval_min not in (60,):
            raise FeedError("only 1h is supported on the free plan")
        self.bar_minutes = interval_min
        self.base = (base_url or self.BASE).rstrip("/")
        self.http = httpx.AsyncClient(timeout=timeout, transport=transport)
        self._clock = clock or (lambda: pd.Timestamp.now(tz="UTC"))
        self.limiter = RateLimiter(per_minute, per_day, self._clock)
        self.last: dict[str, pd.Timestamp] = {}
        self.name = "twelvedata"

    def now(self) -> pd.Timestamp:
        return self._clock()

    @staticmethod
    def td_symbol(symbol: str) -> str:
        return f"{symbol[:3]}/{symbol[3:]}"

    async def _series(self, symbol: str, outputsize: int) -> list[Bar]:
        if not self.limiter.allow():
            raise FeedError("rate limit budget reached (waiting)")
        self.limiter.take()
        r = await self.http.get(f"{self.base}/time_series", params={
            "symbol": self.td_symbol(symbol), "interval": "1h", "outputsize": outputsize, "timezone": "UTC",
            "order": "asc", "apikey": self.key})
        try:
            j = r.json()
        except Exception as ex:
            raise FeedError(f"Twelve Data HTTP {r.status_code}: not JSON") from ex
        if j.get("status") != "ok":
            raise FeedError(f"Twelve Data error {j.get('code')}: {str(j.get('message', ''))[:150]}")
        now = self.now()
        out = []
        for v in j.get("values", []):
            t = pd.Timestamp(v["datetime"]).tz_localize("UTC")
            if t + pd.Timedelta(minutes=self.bar_minutes) > now:
                continue  # still forming
            out.append(Bar(t, float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]), None))
        out.sort(key=lambda b: b.t)
        return out

    def _due(self, symbol: str) -> bool:
        """A new hourly bar can exist once the hour after the last one has closed (+1 min margin)."""
        last = self.last.get(symbol)
        if last is None:
            return True
        return self.now() >= last + pd.Timedelta(minutes=2 * self.bar_minutes) + pd.Timedelta(minutes=1)

    async def poll(self, symbol: str) -> FeedBatch:
        if not self._due(symbol) or not self.limiter.allow():
            return FeedBatch(symbol, [], self.now())
        last = self.last.get(symbol)
        n = 5 if last is None else min(5000, int((self.now() - last) / pd.Timedelta(hours=1)) + 3)
        bars = await self._series(symbol, n)
        if last is not None:
            bars = [b for b in bars if b.t > last]
        if bars:
            self.last[symbol] = bars[-1].t
        return FeedBatch(symbol, bars, self.now())

    async def quote(self, symbol: str) -> tuple[pd.Timestamp, float]:
        """Latest price via `GET /price` (1 credit). Waits up to ~60 s for rate budget."""
        import asyncio
        for _ in range(12):
            if self.limiter.allow():
                break
            await asyncio.sleep(5)
        else:
            raise FeedError("rate limit budget reached")
        self.limiter.take()
        r = await self.http.get(f"{self.base}/price", params={"symbol": self.td_symbol(symbol), "apikey": self.key})
        j = r.json()
        if "price" not in j:
            raise FeedError(f"Twelve Data error {j.get('code')}: {str(j.get('message', ''))[:150]}")
        return self.now(), float(j["price"])

    async def history_h1(self, symbol: str, count: int = 5000) -> pd.DataFrame:
        import asyncio
        while not self.limiter.allow():  # startup: wait for budget instead of failing
            await asyncio.sleep(5)
        bars = await self._series(symbol, count)
        df = pd.DataFrame([(b.t, b.o, b.h, b.l, b.c) for b in bars], columns=["time", "open", "high", "low", "close"])
        df = df.set_index("time").assign(tick_volume=0.0)
        if len(df):
            self.last[symbol] = df.index[-1]
        return df

    async def close(self):
        await self.http.aclose()
