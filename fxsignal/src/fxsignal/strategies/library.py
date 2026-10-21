"""Strategy library: baselines first, then candidate families.

Every rule below is written so that it can be computed at the CLOSE of the signal bar with no
later information. Parameters listed in `GRIDS` are the only values ever searched; the grids
are deliberately small and every run is written to the experiment registry.

Sources and rationale for each family are in docs/RESEARCH_LOG.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import features as F
from ..data.resample import align_to
from .base import Strategy

LONDON = "Europe/London"


def _ctx(s: Strategy, sig: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return s.bars(sig)


def _regime(sig: pd.DataFrame) -> pd.Series:
    return F.regime_label(F.adx(sig, 14), F.rolling_pct_rank(F.atr(sig, 14), 500))


def _london_hour(idx: pd.DatetimeIndex, tf_min: int) -> np.ndarray:
    """London local hour of the bar CLOSE."""
    return (idx + pd.Timedelta(minutes=tf_min)).tz_convert(LONDON).hour.to_numpy()


def _hash_uniform(idx: pd.DatetimeIndex, seed: int) -> np.ndarray:
    """SplitMix64 hash of (timestamp, seed) -> uniform [0, 1)."""
    with np.errstate(over="ignore"):
        x = idx.as_unit("s").asi8.astype(np.uint64) + np.uint64(seed) * np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x = x ^ (x >> np.uint64(31))
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


# ---------------------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------------------
class RandomEntry(Strategy):
    """Null model: random direction at random H1 closes in London/NY hours, ATR stop/target.

    Used to calibrate what "no skill" looks like after costs with identical exit mechanics.
    """

    def __init__(self, p_signal=0.02, stop_atr=1.5, rr=2.0, hold_h=48, seed=0):
        super().__init__("random", "1", "H1", (), dict(p_signal=p_signal, stop_atr=stop_atr, rr=rr,
                                                        hold_h=hold_h, seed=seed))

    def generate(self, sig):
        p = self.params
        # per-bar pseudo-random numbers derived from the timestamp, so the draw for a bar does
        # not depend on how much history was passed in (keeps the null model causal)
        u1, u2 = _hash_uniform(sig.index, p["seed"]), _hash_uniform(sig.index, p["seed"] + 7919)
        a = F.atr(sig, 14)
        lh = _london_hour(sig.index, 60)
        mask = pd.Series((u1 < p["p_signal"]) & (lh >= 8) & (lh <= 17), index=sig.index) & a.notna()
        side = np.where(u2 < 0.5, 1, -1)
        c = sig["close"]
        stop = c - side * p["stop_atr"] * a
        tgt = c + side * p["stop_atr"] * p["rr"] * a
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=30, atr=a, regime=_regime(sig),
                          note="random baseline")


class MACross(Strategy):
    """Baseline trend follower: EMA(fast) crosses EMA(slow) on H1; ATR stop, R-multiple target."""

    def __init__(self, fast=20, slow=100, stop_atr=2.0, rr=2.0, hold_h=120):
        super().__init__("ma_cross", "1", "H1", (), dict(fast=fast, slow=slow, stop_atr=stop_atr, rr=rr, hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        c = sig["close"]
        f, s = F.ema(c, p["fast"]), F.ema(c, p["slow"])
        up = (f > s) & (f.shift(1) <= s.shift(1))
        dn = (f < s) & (f.shift(1) >= s.shift(1))
        a = F.atr(sig, 14)
        side = np.where(up, 1, -1)
        mask = (up | dn) & a.notna()
        stop = c - side * p["stop_atr"] * a
        tgt = c + side * p["stop_atr"] * p["rr"] * a
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note=f"EMA{p['fast']}/{p['slow']} cross")


class DonchianTrend(Strategy):
    """Turtle-style breakout on D1 (built from H1): close beyond the prior N-day channel.

    Exit: trailing M-day opposite channel (updated at each D1 close) or initial 2-ATR stop.
    Time-series momentum in FX is one of the better documented technical effects (see log),
    and also one of the most decayed since the 1990s.
    """

    def __init__(self, n_entry=20, n_exit=10, stop_atr=2.0, hold_d=60):
        super().__init__("donchian_d1", "1", "H1", ("D1",), dict(n_entry=n_entry, n_exit=n_exit, stop_atr=stop_atr,
                                                                  hold_d=hold_d))

    def generate(self, sig):
        p = self.params
        d = _ctx(self, sig)["D1"]
        hi, lo = F.prior_high(d, p["n_entry"]), F.prior_low(d, p["n_entry"])
        a = F.atr(d, 20)
        up = (d["close"] > hi) & (d["close"].shift(1) <= hi.shift(1))
        dn = (d["close"] < lo) & (d["close"].shift(1) >= lo.shift(1))
        side = np.where(up, 1, -1)
        mask = (up | dn) & a.notna()
        c = d["close"]
        stop = c - side * p["stop_atr"] * a
        # Trailing exits known at each D1 close (rolling over the last n_exit days incl. today).
        tr = pd.DataFrame({"long_trail": d["low"].rolling(p["n_exit"]).min(),
                           "short_trail": d["high"].rolling(p["n_exit"]).max()})
        tr.index = d.index + pd.Timedelta(days=1)
        self.trail = tr.dropna()
        return self.frame(d, mask, side, tf="D1", entry_type="market", entry_ref=c, stop=stop, target=np.nan,
                          max_hold_min=p["hold_d"] * 1440, expiry_min=240, atr=a,
                          regime=_regime(d), note=f"{p['n_entry']}-day channel breakout")


# ---------------------------------------------------------------------------------------
# Candidate families
# ---------------------------------------------------------------------------------------
class TrendPullback(Strategy):
    """With-trend pullback on H1.

    Trend: D1 close above/below its EMA(trend_ema) and EMA rising/falling over 5 days.
    Pullback: H1 RSI(14) dipped below `rsi_lo` (above 100-rsi_lo for shorts) within the last
    6 bars, then H1 closes back above EMA(20). Stop below the 10-bar low (structure), bounded
    to [0.8, 3] ATR. Target `rr` R. London/NY hours only.
    """

    def __init__(self, trend_ema=50, rsi_lo=35, rr=2.0, hold_h=72):
        super().__init__("trend_pullback", "1", "H1", ("D1",), dict(trend_ema=trend_ema, rsi_lo=rsi_lo, rr=rr,
                                                                     hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        d = _ctx(self, sig)["D1"]
        de = F.ema(d["close"], p["trend_ema"])
        dctx = pd.DataFrame({"up": (d["close"] > de) & (de > de.shift(5)),
                             "dn": (d["close"] < de) & (de < de.shift(5))})
        al = align_to(sig, "H1", dctx.astype(float), "D1")
        c = sig["close"]
        e20 = F.ema(c, 20)
        r = F.rsi(c, 14)
        a = F.atr(sig, 14)
        lh = _london_hour(sig.index, 60)
        sess = pd.Series((lh >= 8) & (lh <= 17), index=sig.index)
        dipped = (r < p["rsi_lo"]).rolling(6).max().astype(bool)
        popped = (r > 100 - p["rsi_lo"]).rolling(6).max().astype(bool)
        long_ = (al["up"] == 1) & dipped & (c > e20) & (c.shift(1) <= e20.shift(1)) & sess
        short = (al["dn"] == 1) & popped & (c < e20) & (c.shift(1) >= e20.shift(1)) & sess
        lo10, hi10 = sig["low"].rolling(10).min(), sig["high"].rolling(10).max()
        dist_l = (c - lo10 + 0.2 * a).clip(lower=0.8 * a, upper=3 * a)
        dist_s = (hi10 - c + 0.2 * a).clip(lower=0.8 * a, upper=3 * a)
        side = np.where(long_, 1, -1)
        dist = pd.Series(np.where(long_, dist_l, dist_s), index=sig.index)
        stop = c - side * dist
        tgt = c + side * p["rr"] * dist
        mask = (long_ | short) & a.notna()
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note="D1 trend + H1 pullback resumed above/below EMA20")


class BollingerReversion(Strategy):
    """Range mean reversion on H1: in a low-ADX regime, a close outside the band followed by a
    close back inside is faded toward the middle band. Avoids the rollover hours."""

    def __init__(self, adx_max=20, k=2.0, hold_h=24):
        super().__init__("bb_reversion", "1", "H1", (), dict(adx_max=adx_max, k=k, hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        c = sig["close"]
        lo, mid, hi = F.bollinger(c, 20, p["k"])
        ad = F.adx(sig, 14)
        a = F.atr(sig, 14)
        lh = _london_hour(sig.index, 60)
        ok = pd.Series((lh >= 7) & (lh <= 19), index=sig.index) & (ad < p["adx_max"])
        long_ = (c.shift(1) < lo.shift(1)) & (c > lo) & ok
        short = (c.shift(1) > hi.shift(1)) & (c < hi) & ok
        side = np.where(long_, 1, -1)
        ext_l = sig["low"].rolling(3).min() - 0.5 * a
        ext_s = sig["high"].rolling(3).max() + 0.5 * a
        stop = pd.Series(np.where(long_, ext_l, ext_s), index=sig.index)
        tgt = mid
        # require at least 1R of room to the middle band (after spread is unknown here)
        room = (tgt - c) * side / (c - stop).abs()
        mask = (long_ | short) & a.notna() & (room >= 1.0)
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note="low-ADX band re-entry, target middle band")


class SqueezeBreakout(Strategy):
    """Volatility compression -> expansion on H1: ATR(14) in the lowest `pct` of its 500-bar
    history during the prior 5 bars, then a close beyond the 20-bar range. Stop at the opposite
    side of the range (bounded 0.8-3 ATR), target `rr` R."""

    def __init__(self, pct=0.2, rr=2.0, hold_h=48):
        super().__init__("squeeze_breakout", "1", "H1", (), dict(pct=pct, rr=rr, hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        c = sig["close"]
        a = F.atr(sig, 14)
        squeezed = (F.rolling_pct_rank(a, 500) <= p["pct"]).rolling(5).max().astype(bool)
        hi, lo = F.prior_high(sig, 20), F.prior_low(sig, 20)
        lh = _london_hour(sig.index, 60)
        sess = pd.Series((lh >= 7) & (lh <= 18), index=sig.index)
        long_ = squeezed & (c > hi) & sess
        short = squeezed & (c < lo) & sess
        side = np.where(long_, 1, -1)
        dist = pd.Series(np.where(long_, c - lo, hi - c), index=sig.index).clip(lower=0.8 * a, upper=3 * a)
        stop = c - side * dist
        tgt = c + side * p["rr"] * dist
        mask = (long_ | short) & a.notna()
        # one signal per breakout: suppress repeats within 10 bars in the same direction
        sel = mask.copy()
        last = {1: -10**9, -1: -10**9}
        for i in np.flatnonzero(mask.to_numpy()):
            sd = side[i]
            if i - last[sd] < 10:
                sel.iloc[i] = False
            last[sd] = i
        return self.frame(sig, sel, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note="ATR compression then 20-bar range breakout")


class AsianRangeBreakout(Strategy):
    """London-open breakout of the Asian range (00:00-07:00 London time), M15 signals.

    First M15 close beyond the range between 07:00 and 10:00 London. Stop at the range midpoint
    (or opposite side if `stop_mode`='opposite'). Target `rr` R. Flat at 16:00 London. Range
    width must sit between the 20th and 80th percentile of its last 100 days.
    """

    def __init__(self, rr=1.5, stop_mode="mid"):
        super().__init__("asian_breakout", "1", "M15", (), dict(rr=rr, stop_mode=stop_mode))

    def generate(self, sig):
        p = self.params
        loc = sig.index.tz_convert(LONDON)
        day = loc.normalize()
        hr = loc.hour
        asia = (hr < 7)
        g = pd.DataFrame({"h": sig["high"].where(asia), "l": sig["low"].where(asia), "day": day})
        rng = g.groupby("day").agg(h=("h", "max"), l=("l", "min")).dropna()
        rng["w"] = rng["h"] - rng["l"]
        rng["wpct"] = F.rolling_pct_rank(rng["w"], 100)
        m = rng.reindex(day)
        m.index = sig.index
        close_loc = (sig.index + pd.Timedelta(minutes=15)).tz_convert(LONDON)
        window = (close_loc.hour >= 7) & ((close_loc.hour < 10) | ((close_loc.hour == 10) & (close_loc.minute == 0)))
        window = pd.Series(window & (hr >= 7), index=sig.index)
        c = sig["close"]
        okw = (m["wpct"] >= 0.2) & (m["wpct"] <= 0.8)
        long_ = window & okw & (c > m["h"])
        short = window & okw & (c < m["l"])
        first = pd.Series(False, index=sig.index)
        trig = (long_ | short).to_numpy()
        seen = set()
        for i in np.flatnonzero(trig):
            if day[i] not in seen:
                first.iloc[i] = True
                seen.add(day[i])
        side = np.where(long_, 1, -1)
        mid = (m["h"] + m["l"]) / 2
        opp = pd.Series(np.where(long_, m["l"], m["h"]), index=sig.index)
        stop = mid if p["stop_mode"] == "mid" else opp
        dist = (c - stop).abs()
        tgt = c + side * p["rr"] * dist
        # time stop: until 16:00 London of that day
        end = (day + pd.Timedelta(hours=16)).tz_convert("UTC")
        hold = pd.Series(((end - (sig.index + pd.Timedelta(minutes=15))).total_seconds() / 60).to_numpy(), index=sig.index)
        a = F.atr(sig, 14 * 4)
        return self.frame(sig, first & (dist > 0), side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=hold, expiry_min=15, atr=a, regime="",
                          note="Asian range breakout at London open")


class SweepReversal(Strategy):
    """Liquidity-sweep reversal (objective version of 'stop hunt' / 'turtle soup' ideas).

    During 07:00-17:00 London, an H1 bar trades beyond the PRIOR completed day's high (low) by at
    least `min_pen` x D1 ATR and closes back inside it -> fade. Stop beyond the sweep extreme
    (+0.1 H1 ATR). Target `rr` R. Only the first sweep of each side per day.
    """

    def __init__(self, min_pen=0.05, rr=2.0, hold_h=24):
        super().__init__("sweep_reversal", "1", "H1", ("D1",), dict(min_pen=min_pen, rr=rr, hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        d = _ctx(self, sig)["D1"]
        dd = pd.DataFrame({"pdh": d["high"], "pdl": d["low"], "datr": F.atr(d, 14)})
        al = align_to(sig, "H1", dd, "D1")  # last COMPLETED day as of each H1 close
        a = F.atr(sig, 14)
        lh = _london_hour(sig.index, 60)
        sess = pd.Series((lh >= 8) & (lh <= 17), index=sig.index)
        h, l, c = sig["high"], sig["low"], sig["close"]
        pen = p["min_pen"] * al["datr"]
        short = sess & (h > al["pdh"] + pen) & (c < al["pdh"])
        long_ = sess & (l < al["pdl"] - pen) & (c > al["pdl"])
        # first per side per completed-day reference
        key = al["pdh"].astype(str) + al["pdl"].astype(str)
        short = short & ~short.groupby(key).cumsum().gt(1)
        long_ = long_ & ~long_.groupby(key).cumsum().gt(1)
        side = np.where(long_, 1, -1)
        stop = pd.Series(np.where(long_, l - 0.1 * a, h + 0.1 * a), index=sig.index)
        dist = (c - stop).abs()
        tgt = c + side * p["rr"] * dist
        mask = (long_ | short) & a.notna() & (dist > 0.3 * a)
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note="prior-day high/low swept and rejected")


class WeeklyTSMOM(Strategy):
    """Academic time-series momentum, adapted to a signal format: at the first H1 close of each
    week (Monday 00:00 UTC+), go in the direction of the past `lookback_d`-day return. Stop
    `stop_atr` x D1 ATR, exit at the end of the week (time stop ~ 4.5 days)."""

    def __init__(self, lookback_d=60, stop_atr=3.0):
        super().__init__("tsmom_weekly", "1", "H1", ("D1",), dict(lookback_d=lookback_d, stop_atr=stop_atr))

    def generate(self, sig):
        p = self.params
        d = _ctx(self, sig)["D1"]
        ret = d["close"] / d["close"].shift(p["lookback_d"]) - 1
        dd = pd.DataFrame({"ret": ret, "datr": F.atr(d, 20)})
        al = align_to(sig, "H1", dd, "D1")
        # first H1 bar closing on or after Monday 01:00 UTC each week
        t = sig.index + pd.Timedelta(hours=1)
        wk = (t - pd.to_timedelta(t.dayofweek, unit="D")).normalize()
        mon = pd.Series((t.dayofweek == 0) & (t.hour >= 1), index=sig.index)
        # keep only the first Monday bar per week
        seen, sel = set(), np.zeros(len(sig), bool)
        for i in np.flatnonzero(mon.to_numpy()):
            if wk[i] not in seen:
                sel[i] = True
                seen.add(wk[i])
        sel = pd.Series(sel, index=sig.index) & al["ret"].notna() & (al["ret"] != 0)
        side = np.where(al["ret"] > 0, 1, -1)
        c = sig["close"]
        stop = c - side * p["stop_atr"] * al["datr"]
        return self.frame(sig, sel, side, entry_type="market", entry_ref=c, stop=stop, target=np.nan,
                          max_hold_min=int(4.6 * 1440), expiry_min=240, atr=al["datr"], regime=_regime(sig),
                          note=f"{p['lookback_d']}-day return sign")


class UsdFixWindow(Strategy):
    """Round 2 (Krohn, Mueller & Whelan 2024; Ranaldo 2007): the dollar tends to strengthen into
    the 16:00 London WM/R fix and weaken afterwards. USD pairs only.

    leg="pre":  at the H1 close of `start` London hour, long USD; time exit at 16:00 London.
    leg="post": at the 16:00 London H1 close, short USD; time exit `hold_h` hours later.
    Protective stop 1.5 x H1 ATR. No target.
    """

    def __init__(self, leg="pre", start=14, hold_h=3, stop_atr=1.5):
        super().__init__("usd_fix", "1", "H1", (), dict(leg=leg, start=start, hold_h=hold_h, stop_atr=stop_atr))

    def generate(self, sig):
        p = self.params
        sym = sig.attrs.get("symbol", "")
        if "USD" not in sym or sym.startswith("XAU"):
            return self.frame(sig, pd.Series(False, index=sig.index), 1)
        usd_side = 1 if sym.startswith("USD") else -1  # +1 = buying the pair buys USD
        close_loc = (sig.index + pd.Timedelta(hours=1)).tz_convert(LONDON)
        wd = close_loc.dayofweek
        if p["leg"] == "pre":
            at = (close_loc.hour == p["start"]) & (close_loc.minute == 0)
            side, hold = usd_side, (16 - p["start"]) * 60
        else:
            at = (close_loc.hour == 16) & (close_loc.minute == 0)
            side, hold = -usd_side, p["hold_h"] * 60
        a = F.atr(sig, 14)
        mask = pd.Series(at & (wd <= 4), index=sig.index) & a.notna()
        c = sig["close"]
        stop = c - side * p["stop_atr"] * a
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=np.nan,
                          max_hold_min=hold, expiry_min=20, atr=a, regime=_regime(sig),
                          note=f"USD {'into' if p['leg'] == 'pre' else 'after'} the 16:00 London fix")


class RoundNumberBreak(Strategy):
    """Round 2 (Osler 2003): stop-loss orders cluster just beyond round numbers, so crossing a
    100-pip level tends to accelerate. H1 close crosses the level by >= `min_pips` and by less
    than 0.5 ATR, 07-18 London; stop 0.5 ATR back beyond the level; target `rr` R."""

    def __init__(self, rr=1.5, min_pips=3.0, hold_h=24):
        super().__init__("round_break", "1", "H1", (), dict(rr=rr, min_pips=min_pips, hold_h=hold_h))

    def generate(self, sig):
        p = self.params
        sym = sig.attrs.get("symbol", "EURUSD")
        pip = 0.01 if sym.endswith("JPY") else 0.0001
        step = 100 * pip
        c, pc = sig["close"], sig["close"].shift(1)
        a = F.atr(sig, 14)
        lvl_up = np.floor(c / step) * step          # highest round level at/below close
        lvl_dn = np.ceil(c / step) * step           # lowest round level at/above close
        up = (pc < lvl_up) & (c - lvl_up >= p["min_pips"] * pip) & (c - lvl_up < 0.5 * a)
        dn = (pc > lvl_dn) & (lvl_dn - c >= p["min_pips"] * pip) & (lvl_dn - c < 0.5 * a)
        lh = _london_hour(sig.index, 60)
        sess = pd.Series((lh >= 7) & (lh <= 18), index=sig.index)
        up, dn = up & sess, dn & sess
        side = np.where(up, 1, -1)
        lvl = pd.Series(np.where(up, lvl_up, lvl_dn), index=sig.index)
        stop = lvl - side * 0.5 * a
        dist = (c - stop).abs()
        tgt = c + side * p["rr"] * dist
        mask = (up | dn) & a.notna()
        return self.frame(sig, mask, side, entry_type="market", entry_ref=c, stop=stop, target=tgt,
                          max_hold_min=p["hold_h"] * 60, expiry_min=60, atr=a, regime=_regime(sig),
                          note="close through a 100-pip round level")


REGISTRY = {
    "random": RandomEntry,
    "ma_cross": MACross,
    "donchian_d1": DonchianTrend,
    "trend_pullback": TrendPullback,
    "bb_reversion": BollingerReversion,
    "squeeze_breakout": SqueezeBreakout,
    "asian_breakout": AsianRangeBreakout,
    "sweep_reversal": SweepReversal,
    "tsmom_weekly": WeeklyTSMOM,
    "usd_fix": UsdFixWindow,
    "round_break": RoundNumberBreak,
}

# Small, pre-declared grids searched on the development split only.
GRIDS = {
    "ma_cross": [dict(fast=20, slow=100), dict(fast=50, slow=200)],
    "donchian_d1": [dict(n_entry=20, n_exit=10), dict(n_entry=55, n_exit=20)],
    "trend_pullback": [dict(trend_ema=50, rsi_lo=35, rr=2.0), dict(trend_ema=50, rsi_lo=40, rr=1.5),
                       dict(trend_ema=100, rsi_lo=35, rr=2.0)],
    "bb_reversion": [dict(adx_max=20, k=2.0), dict(adx_max=25, k=2.5)],
    "squeeze_breakout": [dict(pct=0.2, rr=2.0), dict(pct=0.1, rr=1.5)],
    "asian_breakout": [dict(rr=1.5, stop_mode="mid"), dict(rr=1.0, stop_mode="opposite")],
    "sweep_reversal": [dict(min_pen=0.05, rr=2.0), dict(min_pen=0.1, rr=1.5)],
    "tsmom_weekly": [dict(lookback_d=60), dict(lookback_d=120)],
    # round 2 (declared in docs/RESEARCH_LOG.md before running)
    "usd_fix": [dict(leg="pre", start=14), dict(leg="post", hold_h=3)],
    "round_break": [dict(rr=1.5), dict(rr=1.0)],
}
