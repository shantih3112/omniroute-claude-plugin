"""Incremental M1 -> M15/H1 bar building for the live service.

Only the newest bucket is touched per incoming bar; history is never recomputed. A bucket is
emitted as COMPLETE when a bar from a later bucket arrives, or when the clock has passed the
bucket end plus a grace period (the last minute may never come in a quiet market). Each
emitted bar carries how many M1 bars it contains so thin bars can be flagged.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

from ..signals.lifecycle import Bar


@dataclass
class Built:
    t: pd.Timestamp
    o: float
    h: float
    l: float
    c: float
    n: int


@dataclass
class Aggregator:
    minutes: int
    max_keep: int = 6000
    grace: pd.Timedelta = pd.Timedelta(seconds=90)
    done: deque = field(default_factory=deque)
    cur: Built | None = None
    late_bars: int = 0

    def _bucket(self, t: pd.Timestamp) -> pd.Timestamp:
        return t.floor(f"{self.minutes}min")

    def add(self, b: Bar) -> list[Built]:
        out = []
        k = self._bucket(b.t)
        if self.done and k <= self.done[-1].t:
            self.late_bars += 1  # bucket already emitted: never re-open or duplicate it
            return out
        if self.cur is not None and k > self.cur.t:
            out.append(self._close())
        if self.cur is None:
            self.cur = Built(k, b.o, b.h, b.l, b.c, 1)
        elif k == self.cur.t:
            self.cur.h, self.cur.l, self.cur.c, self.cur.n = max(self.cur.h, b.h), min(self.cur.l, b.l), b.c, self.cur.n + 1
        # k < cur.t would be an out-of-order bar; the caller's quality gate rejects those earlier
        return out

    def tick(self, now: pd.Timestamp) -> list[Built]:
        if self.cur is not None and now >= self.cur.t + pd.Timedelta(minutes=self.minutes) + self.grace:
            return [self._close()]
        return []

    def _close(self) -> Built:
        b, self.cur = self.cur, None
        self.done.append(b)
        while len(self.done) > self.max_keep:
            self.done.popleft()
        return b

    def frame(self) -> pd.DataFrame:
        if not self.done:
            return pd.DataFrame(columns=["open", "high", "low", "close", "tick_volume"])
        df = pd.DataFrame([(b.t, b.o, b.h, b.l, b.c, float(b.n)) for b in self.done],
                          columns=["time", "open", "high", "low", "close", "tick_volume"]).set_index("time")
        return df

    def seed(self, hist: pd.DataFrame) -> None:
        """Load completed historical bars (already at this timeframe)."""
        for t, r in hist.iterrows():
            self.done.append(Built(pd.Timestamp(t), float(r.open), float(r.high), float(r.low), float(r.close),
                                   int(r.get("tick_volume", 0) or 0)))
        while len(self.done) > self.max_keep:
            self.done.popleft()
