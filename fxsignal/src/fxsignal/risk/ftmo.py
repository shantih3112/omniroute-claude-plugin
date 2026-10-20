"""Versioned FTMO rule profile, rule checks and historical pass/breach simulation.

The profile file records where each rule came from and whether it was verified against FTMO's
own pages. If `verified` is false, `challenge_use_allowed()` returns False and every report
says COMPLIANCE UNVERIFIED. This is deliberate: the official site could not be reached from
the build environment, and secondary sources disagree on some numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..timeutil import PRAGUE


@dataclass(frozen=True)
class FtmoProfile:
    name: str
    version: str
    verified: bool
    initial_balance: float
    profit_target_pct: float
    max_daily_loss_pct: float           # of initial balance
    daily_loss_basis: str               # "prev_day_end_balance" or "max(balance,equity)_at_day_start"
    max_loss_pct: float                 # of initial balance
    max_loss_type: str                  # "static" or "trailing"
    min_trading_days: int
    reset_tz: str
    best_day_rule_pct: float | None
    news_restriction_min: float | None  # funded Standard only, per secondary sources
    weekend_holding_allowed: bool
    sources: tuple[str, ...]
    notes: str = ""

    @staticmethod
    def load(path: str | Path) -> "FtmoProfile":
        d = yaml.safe_load(Path(path).read_text())
        d["sources"] = tuple(d.get("sources", []))
        return FtmoProfile(**d)

    def challenge_use_allowed(self) -> tuple[bool, str]:
        if not self.verified:
            return False, "FTMO rules UNVERIFIED against official source: challenge use blocked"
        return True, "verified"


@dataclass
class DayCheck:
    breached: bool
    reason: str
    daily_floor: float
    overall_floor: float


def floors(p: FtmoProfile, day_start_balance: float, day_start_equity: float) -> tuple[float, float]:
    """Equity levels that must not be touched today."""
    if p.daily_loss_basis == "max(balance,equity)_at_day_start":
        ref = max(day_start_balance, day_start_equity)
    else:
        ref = day_start_balance
    daily = ref - p.max_daily_loss_pct / 100 * p.initial_balance
    overall = p.initial_balance * (1 - p.max_loss_pct / 100)
    return daily, overall


def check_equity(p: FtmoProfile, equity_low: float, day_start_balance: float, day_start_equity: float) -> DayCheck:
    d, o = floors(p, day_start_balance, day_start_equity)
    if equity_low <= o:
        return DayCheck(True, "max loss", d, o)
    if equity_low <= d:
        return DayCheck(True, "max daily loss", d, o)
    return DayCheck(False, "", d, o)


def prague_day(ts: pd.Series | pd.DatetimeIndex) -> pd.Series:
    """Trading-day key under FTMO's reset (midnight Europe/Prague, DST aware)."""
    return pd.Series(pd.DatetimeIndex(ts).tz_convert(PRAGUE).normalize().tz_localize(None), index=getattr(ts, "index", None))


def simulate_challenge(trades: pd.DataFrame, p: FtmoProfile, risk_pct: float, start: pd.Timestamp,
                       max_days: int | None = None) -> dict:
    """Replay closed trades (R multiples, entry/exit times, MAE) from `start`.

    Conservative intraday equity: each trade is assumed to sit at its MAE while open, and all
    trades open on a day are assumed to reach their MAE at the same moment. Risk per trade is
    fixed in money terms from the initial balance (no compounding, no increase to chase the
    target). Returns pass/breach/timeout with the day count.
    """
    t = trades[(trades["status"] == "filled") & (pd.to_datetime(trades["entry_time"]) >= start)]
    t = t.sort_values("entry_time")
    if max_days is not None:
        t = t[pd.to_datetime(t["entry_time"]) < start + pd.Timedelta(days=max_days)]
    risk_money = p.initial_balance * risk_pct / 100
    bal = p.initial_balance
    trading_days: set = set()
    if t.empty:
        return dict(result="no_trades", days=0, trading_days=0, final_pct=0.0)
    t = t.assign(eday=prague_day(pd.to_datetime(t["entry_time"])).to_numpy(),
                 xday=prague_day(pd.to_datetime(t["exit_time"])).to_numpy())
    days = pd.date_range(t["eday"].min(), t["xday"].max(), freq="D")
    for day in days:
        day_start_bal = bal
        open_today = t[(t["eday"] <= day) & (t["xday"] >= day)]
        if len(open_today):
            trading_days.update(open_today["eday"][open_today["eday"] == day].tolist())
        worst = (open_today["mae_r"].clip(upper=0) * risk_money).sum()
        closing = t[t["xday"] == day]
        # realised P/L of trades closing today (their full R)
        realised = (closing["r_net"] * risk_money).sum()
        chk = check_equity(p, bal + worst, day_start_bal, day_start_bal)
        if chk.breached:
            return dict(result="breach_" + chk.reason.replace(" ", "_"), days=(day - days[0]).days + 1,
                        trading_days=len(trading_days), final_pct=100 * (bal + worst) / p.initial_balance - 100)
        bal += realised
        chk = check_equity(p, bal, day_start_bal, day_start_bal)
        if chk.breached:
            return dict(result="breach_" + chk.reason.replace(" ", "_"), days=(day - days[0]).days + 1,
                        trading_days=len(trading_days), final_pct=100 * bal / p.initial_balance - 100)
        no_open_left = t[(t["eday"] <= day) & (t["xday"] > day)].empty
        if bal >= p.initial_balance * (1 + p.profit_target_pct / 100) and len(trading_days) >= p.min_trading_days \
                and no_open_left:
            return dict(result="pass", days=(day - days[0]).days + 1, trading_days=len(trading_days),
                        final_pct=100 * bal / p.initial_balance - 100)
    return dict(result="incomplete", days=len(days), trading_days=len(trading_days),
                final_pct=100 * bal / p.initial_balance - 100)


def pass_rate_study(trades: pd.DataFrame, p: FtmoProfile, risk_pct: float, n_starts: int = 60,
                    max_days: int = 120, seed: int = 0) -> dict:
    """Many historical start dates; Wilson 90% intervals on pass / breach rates."""
    t = trades[trades["status"] == "filled"]
    if t.empty:
        return {"starts": 0}
    times = pd.to_datetime(t["entry_time"]).sort_values()
    lo, hi = times.iloc[0], times.iloc[-1] - pd.Timedelta(days=max_days)
    if hi <= lo:
        return {"starts": 0, "note": "history shorter than max_days"}
    starts = pd.date_range(lo, hi, periods=n_starts)
    res = [simulate_challenge(trades, p, risk_pct, s, max_days) for s in starts]
    outc = pd.Series([r["result"] for r in res])
    n = len(outc)

    def wilson(k):
        z = 1.645
        ph = k / n
        den = 1 + z * z / n
        c = (ph + z * z / (2 * n)) / den
        h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
        return [round(100 * max(0, c - h), 1), round(100 * min(1, c + h), 1)]

    k_pass = int((outc == "pass").sum())
    k_breach = int(outc.str.startswith("breach").sum())
    days_pass = [r["days"] for r in res if r["result"] == "pass"]
    return dict(starts=n, pass_pct=round(100 * k_pass / n, 1), pass_ci90=wilson(k_pass),
                breach_pct=round(100 * k_breach / n, 1), breach_ci90=wilson(k_breach),
                median_days_to_pass=float(np.median(days_pass)) if days_pass else None,
                outcomes=outc.value_counts().to_dict(),
                caveat="overlapping start dates are not independent; intervals are optimistic")
