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
    def __init__(self, m1: dict[str, pd.DataFrame], start: pd.Timestamp, spread_model=None):
        self.m1 = {k: v.sort_index() for k, v in m1.items()}
        self.clock = pd.Timestamp(start)
        self._cursor = {k: int(v.index.searchsorted(self.clock)) for k, v in self.m1.items()}
        self.spread_model = spread_model
        self.name = "replay"

    def now(self) -> pd.Timestamp:
        return self.clock

    def advance(self, minutes: int = 1) -> None:
        self.clock = self.clock + pd.Timedelta(minutes=minutes)

    async def poll(self, symbol: str) -> FeedBatch:
        df = self.m1[symbol]
        i = self._cursor[symbol]
        out = []
        # a bar is complete once the clock has passed its close
        while i < len(df) and df.index[i] + pd.Timedelta(minutes=1) <= self.clock:
            r = df.iloc[i]
            sp = self.spread_model(symbol, df.index[i]) if self.spread_model else None
            out.append(Bar(df.index[i], float(r.open), float(r.high), float(r.low), float(r.close), sp))
            i += 1
        self._cursor[symbol] = i
        return FeedBatch(symbol, out, self.clock)

    def history(self, symbol: str, before: pd.Timestamp) -> pd.DataFrame:
        df = self.m1[symbol]
        return df[df.index + pd.Timedelta(minutes=1) <= before]


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
