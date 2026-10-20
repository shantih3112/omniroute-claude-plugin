"""Trade-level execution simulator on BID bars with a modelled ask.

Conservative conventions (see docs/SCORECARD.md §2):
* entry happens at the first execution bar whose OPEN is at/after `signal time + delay`;
* longs fill at ask (= bid + spread), shorts at bid; exits the reverse;
* inside one bar we do not know the path, so if stop and target are both touched the STOP wins;
* a bar that opens beyond the stop fills at that open (gap), plus stop slippage;
* a follower whose fill is more than `max_dev_r` x (planned risk) worse than the signal's
  reference price does NOT enter ("do not chase"); recorded as `missed_chase`;
* a fill on the wrong side of the stop, or after the signal expired, is recorded as missed;
* limit signals fill only if the modelled ask (long) / bid (short) trades through the level
  before expiry; the fill price is the level, or the open if it gapped through favourably.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..instruments import Instrument, spread_multiplier
from ..timeutil import open_hours_between

# Approximate quote->USD rates used ONLY to express USD commissions in price units.
# The commission is ~0.5 pip, so a 10-20 % error here is ~0.1 pip; documented in ASSUMPTIONS.
QUOTE_USD = {"USD": 1.0, "JPY": 1 / 120.0, "CHF": 1.05, "GBP": 1.3, "CAD": 0.76, "AUD": 0.7, "EUR": 1.12}

HOUR_MULT = np.array([spread_multiplier(h) for h in range(24)])


@dataclass(frozen=True)
class CostScenario:
    name: str = "base"
    spread_mult: float = 1.0
    stop_slip_pips: float = 0.2
    entry_slip_pips: float = 0.1
    commission_mult: float = 1.0
    swap_mult: float = 1.0


BASE = CostScenario()
STRESS_15 = CostScenario("stress1.5x", 1.5, 0.5, 0.2, 1.0, 1.5)
STRESS_20 = CostScenario("stress2x", 2.0, 0.5, 0.3, 1.0, 2.0)
ZERO = CostScenario("zero", 0.0, 0.0, 0.0, 0.0, 0.0)


class ExecSeries:
    """Execution bars as contiguous numpy arrays (bid OHLC, UTC open times)."""

    def __init__(self, df: pd.DataFrame, tf_minutes: int):
        self.t = df.index.as_unit("ns").asi8.copy()  # ns (pandas 3 may default to us)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.hour = df.index.hour.to_numpy()
        self.tf_ns = int(tf_minutes * 60e9)
        # data holes: >= 2h of regular market time missing before bar i (vendor outage, not a
        # weekend/holiday). Trades spanning a hole are not scored: their outcome is unknown.
        hole = np.zeros(len(self.t), bool)
        gaps = np.diff(self.t) / 60e9
        for i in np.flatnonzero(gaps > max(4 * tf_minutes, 120)):
            if open_hours_between(df.index[i], df.index[i + 1]) >= 2:
                hole[i + 1] = True
        self.hole_cum = np.cumsum(hole)

    def __len__(self):
        return len(self.t)


def _spread(inst: Instrument, hour: int, cs: CostScenario) -> float:
    return inst.spread_pips * HOUR_MULT[hour] * cs.spread_mult * inst.pip_size


def _commission_price(inst: Instrument, cs: CostScenario) -> float:
    """Round-trip commission per unit of base currency, in quote price units."""
    per_lot = 2 * inst.commission_usd_per_lot_side * cs.commission_mult
    return per_lot / QUOTE_USD.get(inst.quote, 1.0) / inst.contract_size


def rollovers(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """Financing nights between a and b: 21:00 UTC rollovers crossed, Wednesday counted 3x
    (approximation of the 17:00 New York rollover and the T+2 weekend roll)."""
    n = 0
    d = a.normalize() + pd.Timedelta(hours=21)
    if d <= a:
        d += pd.Timedelta(days=1)
    while d <= b:
        n += 3 if d.dayofweek == 2 else 1
        d += pd.Timedelta(days=1)
    return n


TRADE_COLS = ["signal_time", "side", "status", "entry_time", "entry", "stop", "target", "exit_time", "exit",
              "exit_reason", "risk_price", "r_gross", "r_net", "pips_net", "cost_r", "mae_r", "mfe_r", "nights",
              "delay_min", "entry_dev_r"]


def simulate(signals: pd.DataFrame, ex: ExecSeries, inst: Instrument, cs: CostScenario = BASE,
             delay_min: float = 0.0, max_dev_r: float = 0.25, max_fav_r: float = 0.5,
             trail: pd.DataFrame | None = None,
             one_at_a_time: bool = True) -> pd.DataFrame:
    """Simulate every signal. With `one_at_a_time`, a new signal for this instrument/strategy
    is skipped (status `skipped_open`) while a previous one is still open - a follower would
    not stack the same idea."""
    rows = []
    comm = _commission_price(inst, cs)
    pip = inst.pip_size
    tr_t = tr_l = tr_s = None
    if trail is not None and len(trail):
        tr_t = pd.DatetimeIndex(trail.index).as_unit("ns").asi8
        tr_l = trail["long_trail"].to_numpy(float)
        tr_s = trail["short_trail"].to_numpy(float)
    busy_until = -1
    n = len(ex)
    for s in signals.itertuples(index=False):
        sig_ns = pd.Timestamp(s.time).value
        side = int(s.side)
        base = dict(signal_time=s.time, side=side, stop=s.stop, target=s.target, delay_min=delay_min)
        if one_at_a_time and sig_ns < busy_until:
            rows.append(dict(base, status="skipped_open"))
            continue
        avail = sig_ns + int(delay_min * 60e9)
        expiry = sig_ns + int(s.expiry_min * 60e9)
        i0 = int(np.searchsorted(ex.t, avail, side="left"))
        if i0 >= n:
            rows.append(dict(base, status="no_data"))
            continue
        stop, target = float(s.stop), float(s.target) if not pd.isna(s.target) else np.nan
        planned_risk = abs(float(s.entry_ref) - stop)
        if s.entry_type != "limit" and side == 1:
            planned_risk += _spread(inst, ex.hour[min(i0, n - 1)], cs)  # long reference is the ask
        if planned_risk <= 0:
            rows.append(dict(base, status="invalid"))
            continue
        # ---- entry ------------------------------------------------------------------
        entry = np.nan
        ie = -1
        if s.entry_type == "limit":
            lvl = float(s.entry_ref)
            for i in range(i0, n):
                if ex.t[i] > expiry:
                    break
                sp = _spread(inst, ex.hour[i], cs)
                if side == 1 and ex.l[i] + sp <= lvl:
                    entry, ie = min(lvl, ex.o[i] + sp), i
                    break
                if side == -1 and ex.h[i] >= lvl:
                    entry, ie = max(lvl, ex.o[i]), i
                    break
            if ie < 0:
                rows.append(dict(base, status="expired_unfilled"))
                continue
        else:
            if ex.t[i0] > expiry:
                rows.append(dict(base, status="missed_closed"))
                continue
            sp = _spread(inst, ex.hour[i0], cs)
            slip = cs.entry_slip_pips * pip
            entry = ex.o[i0] + sp + slip if side == 1 else ex.o[i0] - slip
            ie = i0
            ref = float(s.entry_ref) + (sp if side == 1 else 0.0)
            dev_r = (entry - ref) * side / planned_risk
            base["entry_dev_r"] = dev_r
            if dev_r > max_dev_r:
                rows.append(dict(base, status="missed_chase", entry_time=pd.Timestamp(ex.t[i0], tz="UTC")))
                continue
            if dev_r < -max_fav_r:
                # price already ran most of the way to the stop: the published setup is no longer
                # the one that was analysed (entry zone is two-sided)
                rows.append(dict(base, status="missed_zone", entry_time=pd.Timestamp(ex.t[i0], tz="UTC")))
                continue
        if (entry - stop) * side <= 0:
            rows.append(dict(base, status="missed_beyond_stop"))
            continue
        # R is measured in units of the PLANNED risk (signal reference incl. spread -> stop):
        # a follower sizes the position from the published levels, so that is what one R costs.
        risk = planned_risk if s.entry_type != "limit" else (entry - stop) * side
        # ---- exit (vectorised over chunks of bars) ----------------------------------
        hold_end = ex.t[ie] + int(s.max_hold_min * 60e9)
        ix, exit_px, reason, mae, mfe = _find_exit(ex, inst, cs, ie, side, entry, stop, target, risk, hold_end,
                                                    sig_ns, tr_t, tr_l, tr_s)
        if ix < 0:
            rows.append(dict(base, status="open_at_end", entry_time=pd.Timestamp(ex.t[ie], tz="UTC"), entry=entry))
            continue
        if ex.hole_cum[ix] != ex.hole_cum[ie]:
            rows.append(dict(base, status="data_gap", entry_time=pd.Timestamp(ex.t[ie], tz="UTC"), entry=entry))
            continue
        nights = rollovers(pd.Timestamp(ex.t[ie], tz="UTC"), pd.Timestamp(ex.t[ix], tz="UTC"))
        swap = nights * inst.swap_pips_per_night * cs.swap_mult * pip
        gross = (exit_px - entry) * side
        net = gross - comm - swap
        exit_time = ex.t[ix] + (0 if reason == "time" else ex.tf_ns)
        rows.append(dict(base, status="filled", entry_time=pd.Timestamp(ex.t[ie], tz="UTC"), entry=entry,
                         exit_time=pd.Timestamp(exit_time, tz="UTC"), exit=exit_px, exit_reason=reason,
                         risk_price=risk, r_gross=gross / risk, r_net=net / risk, pips_net=net / pip,
                         cost_r=(gross - net) / risk, mae_r=mae, mfe_r=mfe, nights=nights))
        busy_until = exit_time
    out = pd.DataFrame(rows)
    for c in TRADE_COLS:
        if c not in out:
            out[c] = np.nan
    return out[TRADE_COLS]


def _find_exit(ex: ExecSeries, inst: Instrument, cs: CostScenario, ie: int, side: int, entry: float, stop: float,
               target: float, risk: float, hold_end: int, sig_ns: int, tr_t, tr_l, tr_s, chunk: int = 4096):
    """First bar at/after `ie` where the trade exits. Returns (index, price, reason, mae_r, mfe_r)."""
    n = len(ex)
    pip = inst.pip_size
    slip = cs.stop_slip_pips * pip
    mae = mfe = 0.0
    cur_stop = stop
    a = ie
    while a < n:
        b = min(n, a + chunk)
        sl = slice(a, b)
        sp = inst.spread_pips * HOUR_MULT[ex.hour[sl]] * cs.spread_mult * pip
        o, h, l = ex.o[sl], ex.h[sl], ex.l[sl]
        t = ex.t[sl]
        # effective stop per bar: trailing levels published before the bar opened ratchet the stop
        if tr_t is not None:
            k = np.searchsorted(tr_t, t, side="right") - 1
            lv = np.where(k >= 0, (tr_l if side == 1 else tr_s)[np.clip(k, 0, None)], np.nan)
            valid = (k >= 0) & (tr_t[np.clip(k, 0, None)] > sig_ns) & ~np.isnan(lv)
            if a == ie:
                valid[0] = False  # the entry bar uses the initial stop
            lv = np.where(valid, lv, cur_stop)
            st = np.maximum.accumulate(np.maximum(lv, cur_stop)) if side == 1 else \
                np.minimum.accumulate(np.minimum(lv, cur_stop))
        else:
            st = np.full(len(t), cur_stop)
        is_first = np.zeros(len(t), bool)
        if a == ie:
            is_first[0] = True
        time_exit = (t >= hold_end) & ~is_first
        if side == 1:
            gap = (o <= st) & ~is_first
            hit_s = l <= st
            hit_t = (h >= target) if not np.isnan(target) else np.zeros(len(t), bool)
            adverse, favour = (l - entry) / risk, (h - entry) / risk
        else:
            ao = o + sp
            gap = (ao >= st) & ~is_first
            hit_s = (h + sp) >= st
            hit_t = ((l + sp) <= target) if not np.isnan(target) else np.zeros(len(t), bool)
            adverse, favour = (entry - (h + sp)) / risk, (entry - (l + sp)) / risk
        any_exit = time_exit | gap | hit_s | hit_t
        j = int(np.argmax(any_exit)) if any_exit.any() else -1
        if j < 0:
            mae = min(mae, float(adverse.min()))
            mfe = max(mfe, float(favour.max()))
            cur_stop = float(st[-1])
            a = b
            continue
        i = a + j
        trailing = st[j] != stop
        rs = "trail" if trailing else "stop"
        if time_exit[j]:
            px = o[j] if side == 1 else o[j] + sp[j]
            r = "time"
        elif gap[j]:
            px = (o[j] - slip) if side == 1 else (o[j] + sp[j] + slip)
            r = rs
        elif hit_s[j]:
            px = (st[j] - slip) if side == 1 else (st[j] + slip)
            r = rs
        else:
            if is_first[j]:
                px = target
            else:
                px = max(o[j], target) if side == 1 else min(o[j] + sp[j], target)
            r = "target"
        if j > 0:
            mae = min(mae, float(adverse[:j].min()))
            mfe = max(mfe, float(favour[:j].max()))
        if r != "time":
            mae = min(mae, float(adverse[j]))
            mfe = max(mfe, float(favour[j]) if r == "target" else mfe)
        return i, float(px), r, mae, mfe
    return -1, np.nan, "", mae, mfe
