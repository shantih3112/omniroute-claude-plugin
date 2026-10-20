"""Independent, deterministic risk engine.

Sits above every strategy. A strategy proposes; this engine approves or rejects, with reasons.
Nothing here can be changed by a strategy, by news content or by an LLM: limits come from the
config file only, and the prohibited behaviours (martingale, grids, doubling after losses,
risk increases to recover losses or to chase a profit target) are structurally impossible
because risk per trade is a constant from config, capped, and never a function of past P/L
except to REDUCE it.

Scope, stated plainly: without read-only access to the follower's broker account, this engine
enforces limits on the SYSTEM'S OWN PAPER PORTFOLIO (the signals it has issued). It cannot see
or enforce a follower's real account-wide exposure.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..instruments import Instrument


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.5
    hard_max_risk_per_trade_pct: float = 1.0
    max_open_risk_pct: float = 2.0
    max_currency_exposure_pct: float = 1.0
    max_pair_correlation: float = 0.7
    daily_loss_stop_pct: float = 3.0
    overall_drawdown_stop_pct: float = 8.0
    losing_streak_pause: int = 6
    losing_streak_risk_scale: float = 0.5   # after `losing_streak_reduce` losses, risk is HALVED
    losing_streak_reduce: int = 4
    max_spread_multiple: float = 2.0        # vs the instrument's typical spread
    max_data_age_s: float = 180.0
    min_reward_risk_after_costs: float = 1.0
    kill_switch_file: str = "var/KILL_SWITCH"

    def __post_init__(self):
        if self.risk_per_trade_pct > self.hard_max_risk_per_trade_pct:
            raise ValueError("risk_per_trade_pct exceeds hard maximum")
        if self.losing_streak_risk_scale > 1.0:
            raise ValueError("losing-streak scaling may only reduce risk")


@dataclass
class OpenRisk:
    signal_id: str
    symbol: str
    side: int
    risk_pct: float
    base: str
    quote: str


@dataclass
class PortfolioState:
    """Paper portfolio of the system's own signals (not a follower's account)."""
    equity_pct: float = 100.0            # equity as % of starting capital
    peak_equity_pct: float = 100.0
    day_start_equity_pct: float = 100.0
    open: list[OpenRisk] = field(default_factory=list)
    consecutive_losses: int = 0
    paused: bool = False
    pause_reason: str = ""


@dataclass
class Proposal:
    signal_id: str
    symbol: str
    side: int
    entry: float
    stop: float
    target: float | None
    spread_now_pips: float
    data_age_s: float
    expected_cost_r: float = 0.0


@dataclass
class Decision:
    approved: bool
    risk_pct: float
    reasons: list[str]
    warnings: list[str] = field(default_factory=list)


def currency_exposure(open_: list[OpenRisk]) -> dict[str, float]:
    """Signed risk per currency: long EURUSD at 0.5% = EUR +0.5, USD -0.5."""
    ex: dict[str, float] = {}
    for o in open_:
        ex[o.base] = ex.get(o.base, 0.0) + o.side * o.risk_pct
        ex[o.quote] = ex.get(o.quote, 0.0) - o.side * o.risk_pct
    return ex


class RiskEngine:
    def __init__(self, cfg: RiskConfig, base_dir: Path | None = None):
        self.cfg = cfg
        self.base_dir = base_dir or Path.cwd()

    # -- kill switch ---------------------------------------------------------------------
    def kill_switch_on(self) -> bool:
        p = Path(self.cfg.kill_switch_file)
        p = p if p.is_absolute() else self.base_dir / p
        return p.exists() or os.environ.get("FXSIGNAL_KILL", "") == "1"

    def risk_for_next_trade(self, st: PortfolioState) -> float:
        r = self.cfg.risk_per_trade_pct
        if st.consecutive_losses >= self.cfg.losing_streak_reduce:
            r *= self.cfg.losing_streak_risk_scale
        return min(r, self.cfg.hard_max_risk_per_trade_pct)

    def evaluate(self, p: Proposal, inst: Instrument, st: PortfolioState,
                 corr: dict[tuple[str, str], float] | None = None) -> Decision:
        c = self.cfg
        reasons: list[str] = []
        warn: list[str] = []
        if self.kill_switch_on():
            reasons.append("kill switch is ON")
        if st.paused:
            reasons.append(f"signals paused: {st.pause_reason or 'by admin'}")
        if p.data_age_s > c.max_data_age_s:
            reasons.append(f"price data stale ({p.data_age_s:.0f}s old)")
        if p.spread_now_pips > c.max_spread_multiple * inst.spread_pips:
            reasons.append(f"spread {p.spread_now_pips:.1f} pips > {c.max_spread_multiple}x typical")
        dd_day = st.day_start_equity_pct - st.equity_pct
        if dd_day >= c.daily_loss_stop_pct - 1e-9:
            reasons.append(f"daily loss {dd_day:.2f}% reached stop {c.daily_loss_stop_pct}%")
        dd_all = 100 * (1 - st.equity_pct / st.peak_equity_pct)
        if dd_all >= c.overall_drawdown_stop_pct - 1e-9:
            reasons.append(f"drawdown {dd_all:.2f}% reached stop {c.overall_drawdown_stop_pct}%")
        if st.consecutive_losses >= c.losing_streak_pause:
            reasons.append(f"{st.consecutive_losses} consecutive losses: new signals paused for review")
        risk = self.risk_for_next_trade(st)
        if risk < c.risk_per_trade_pct:
            warn.append(f"risk reduced to {risk:.2f}% after {st.consecutive_losses} consecutive losses")
        open_risk = sum(o.risk_pct for o in st.open)
        if open_risk + risk > c.max_open_risk_pct + 1e-9:
            reasons.append(f"open risk {open_risk:.2f}% + {risk:.2f}% > limit {c.max_open_risk_pct}%")
        ex = currency_exposure(st.open + [OpenRisk(p.signal_id, p.symbol, p.side, risk, inst.base, inst.quote)])
        for ccy in (inst.base, inst.quote):
            if abs(ex.get(ccy, 0.0)) > c.max_currency_exposure_pct + 1e-9:
                reasons.append(f"{ccy} net exposure would be {ex[ccy]:+.2f}% (limit ±{c.max_currency_exposure_pct}%)")
        if any(o.symbol == p.symbol for o in st.open):
            reasons.append(f"already an open signal on {p.symbol}")
        if corr:
            for o in st.open:
                rho = corr.get((p.symbol, o.symbol), corr.get((o.symbol, p.symbol)))
                if rho is not None and rho * p.side * o.side > c.max_pair_correlation:
                    reasons.append(f"effectively the same bet as open {o.symbol} signal (ρ={rho:+.2f})")
        dist = abs(p.entry - p.stop)
        if dist <= 0 or (p.side == 1 and p.stop >= p.entry) or (p.side == -1 and p.stop <= p.entry):
            reasons.append("stop on wrong side of entry")
        if p.target is not None and not np.isnan(p.target) and dist > 0:
            rr = abs(p.target - p.entry) / dist - p.expected_cost_r
            if rr < c.min_reward_risk_after_costs:
                reasons.append(f"reward:risk after costs {rr:.2f} < {c.min_reward_risk_after_costs}")
        return Decision(not reasons, risk if not reasons else 0.0, reasons, warn)
