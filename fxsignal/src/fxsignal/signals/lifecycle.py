"""Incremental paper outcome tracking for published signals.

Applies, one completed M1 bar at a time, exactly the fill and exit conventions of the research
engine (backtest/engine.py) so that forward paper results are comparable with the backtest:
paper entry at the open of the first bar starting at/after `published + paper_delay`, ask for
longs, stop-first inside a bar, gaps fill at the open, R in units of planned risk, costs
(commission + financing) deducted. tests/test_lifecycle.py checks parity with the engine.

Each transition is appended to the store as an event and returned so the caller can publish an
update message. Nothing is ever edited in place.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.engine import BASE, CostScenario, _commission_price, _spread, rollovers
from ..instruments import Instrument


@dataclass
class Bar:
    t: pd.Timestamp     # open time, UTC
    o: float
    h: float
    l: float
    c: float
    spread: float | None = None   # measured spread (price units) if the feed provides ask


@dataclass
class Transition:
    signal_id: str
    kind: str            # triggered | missed | expired | closed
    ts: pd.Timestamp
    price: float | None
    r_result: float | None
    detail: dict


class PaperTracker:
    def __init__(self, inst: Instrument, cs: CostScenario = BASE, paper_delay_min: float = 1.0,
                 max_dev_r: float = 0.25, max_fav_r: float = 0.5):
        self.inst, self.cs = inst, cs
        self.delay = pd.Timedelta(minutes=paper_delay_min)
        self.max_dev_r, self.max_fav_r = max_dev_r, max_fav_r

    def _spr(self, bar: Bar) -> float:
        return bar.spread if bar.spread is not None else _spread(self.inst, bar.t.hour, self.cs)

    def step(self, sig: dict, state: dict, bar: Bar) -> tuple[dict, list[Transition]]:
        """Advance one signal by one completed bar. `state` is the tracker's mutable view
        (persisted by the caller): phase, entry, entry_t, nights_start, mae."""
        side = int(sig["side"])
        sid = sig["id"]
        phase = state.get("phase", "pending")
        pub = pd.Timestamp(state.get("published_at") or sig["created_at"])
        if phase == "pending":
            if bar.t < pub + self.delay:
                return state, []
            if bar.t > pd.Timestamp(sig["expires_at"]):
                return dict(state, phase="done"), [Transition(sid, "expired", bar.t, None, None,
                                                             {"why": "no executable price before expiry"})]
            state, trs = self._enter(sig, state, bar.t, bar.o, self._spr(bar))
            if state.get("phase") != "open":
                return state, trs
            # the entry bar itself can also hit stop/target after the open
            state2, tr2 = self._exit_check(sig, state, bar, first=True)
            return state2, trs + ([tr2] if tr2 is not None else [])
        if phase == "open":
            if bar.t < pd.Timestamp(state["entry_t"]):
                # entered from a quote in the middle of this bar: the part before the entry is
                # unknown, so only the stop is checked (conservative; a target there is ignored)
                st, tr = self._exit_check(dict(sig, target=None), state, bar, first=True)
            else:
                st, tr = self._exit_check(sig, state, bar, first=False)
            return st, ([tr] if tr is not None else [])
        return state, []

    def enter_at(self, sig: dict, state: dict, t: pd.Timestamp, price: float,
                 spread: float | None = None) -> tuple[dict, list[Transition]]:
        """Paper entry from a live quote taken at publication (hourly feeds), same zone rules."""
        if state.get("phase", "pending") != "pending":
            return state, []
        if t > pd.Timestamp(sig["expires_at"]):
            return dict(state, phase="done"), [Transition(sig["id"], "expired", t, None, None,
                                                          {"why": "no executable price before expiry"})]
        sp = spread if spread is not None else _spread(self.inst, t.hour, self.cs)
        st, trs = self._enter(sig, state, t, price, sp)
        for tr in trs:
            tr.detail["source"] = "quote at publication"
        return st, trs

    def _enter(self, sig: dict, state: dict, t: pd.Timestamp, bid: float, sp: float):
        side = int(sig["side"])
        sid = sig["id"]
        pip = self.inst.pip_size
        entry = bid + sp + self.cs.entry_slip_pips * pip if side == 1 else bid - self.cs.entry_slip_pips * pip
        ref = sig["entry_ref"] + (sp if side == 1 else 0.0)
        planned = abs(sig["entry_ref"] - sig["stop"]) + (sp if side == 1 else 0.0)
        dev = (entry - ref) * side / planned
        if dev > self.max_dev_r or dev < -self.max_fav_r or (entry - sig["stop"]) * side <= 0:
            return dict(state, phase="done"), [Transition(
                sid, "missed", t, entry, None,
                {"why": "price outside the entry zone - do not chase", "deviation_r": round(dev, 3)})]
        state = dict(state, phase="open", entry=entry, entry_t=str(t), planned=planned, mae=0.0)
        return state, [Transition(sid, "triggered", t, entry, None, {"deviation_r": round(dev, 3)})]

    def _exit_check(self, sig, state, bar: Bar, first: bool):
        side = int(sig["side"])
        stop, target = sig["stop"], sig["target"]
        target = np.nan if target is None else target
        entry, planned = state["entry"], state["planned"]
        sp = self._spr(bar)
        pip = self.inst.pip_size
        slip = self.cs.stop_slip_pips * pip
        hold_end = pd.Timestamp(state["entry_t"]) + pd.Timedelta(minutes=sig["max_hold_min"])
        px = reason = None
        if not first and bar.t >= hold_end:
            px, reason = (bar.o if side == 1 else bar.o + sp), "time"
        elif side == 1:
            if not first and bar.o <= stop:
                px, reason = bar.o - slip, "stop"
            elif bar.l <= stop:
                px, reason = stop - slip, "stop"
            elif not np.isnan(target) and bar.h >= target:
                px, reason = (target if first else max(bar.o, target)), "target"
            state["mae"] = min(state["mae"], (bar.l - entry) / planned)
        else:
            ao = bar.o + sp
            if not first and ao >= stop:
                px, reason = ao + slip, "stop"
            elif bar.h + sp >= stop:
                px, reason = stop + slip, "stop"
            elif not np.isnan(target) and bar.l + sp <= target:
                px, reason = (target if first else min(ao, target)), "target"
            state["mae"] = min(state["mae"], (entry - (bar.h + sp)) / planned)
        if reason is None:
            return state, None
        gross = (px - entry) * side
        nights = rollovers(pd.Timestamp(state["entry_t"]), bar.t)
        costs = _commission_price(self.inst, self.cs) + nights * self.inst.swap_pips_per_night * self.cs.swap_mult * pip
        r = (gross - costs) / planned
        ts = bar.t + (pd.Timedelta(0) if reason == "time" else pd.Timedelta(minutes=1))
        return dict(state, phase="done"), Transition(sig["id"], "closed", ts, px, r,
                                                     {"reason": reason, "mae_r": round(state["mae"], 3),
                                                      "nights": nights})
