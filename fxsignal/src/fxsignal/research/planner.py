"""Illustrative capital-planning Monte Carlo.

Everything here is driven by ASSUMED inputs that the user chooses; nothing is a forecast and no
input comes from a validated strategy (none exists yet). Trading returns and deposits are kept
separate, recurring costs are charged whether or not trading makes money, and a run that falls
below `ruin_floor` stops trading (capital exhausted for practical purposes).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PlanInputs:
    start_capital: float = 1_000.0
    monthly_contribution: float = 0.0
    monthly_costs: float = 15.0          # hosting/data/etc., paid from the account
    years: int = 10
    trades_per_month: float = 20.0
    risk_pct: float = 0.5
    expectancy_r: float = 0.0            # ASSUMED mean R per trade after costs
    r_sd: float = 1.2                    # ASSUMED sd of R per trade
    monthly_withdrawal_pct_above_hwm: float = 0.0
    ruin_floor: float = 100.0            # below this, stop (min-lot sizing no longer possible)
    min_lot_risk_floor: float = 0.0      # account size below which 0.01 lot exceeds risk budget
    n_paths: int = 5_000
    seed: int = 1


def simulate(p: PlanInputs) -> dict:
    rng = np.random.default_rng(p.seed)
    months = p.years * 12
    eq = np.full(p.n_paths, p.start_capital, float)
    deposits = np.full(p.n_paths, p.start_capital, float)
    withdrawn = np.zeros(p.n_paths)
    trading_pnl = np.zeros(p.n_paths)
    costs_paid = np.zeros(p.n_paths)
    hwm = eq.copy()
    alive = np.ones(p.n_paths, bool)
    month_dd = np.zeros(p.n_paths)
    paths = np.empty((months + 1, p.n_paths))
    paths[0] = eq
    for m in range(months):
        n = rng.poisson(p.trades_per_month, p.n_paths)
        # sum of n trades' R ~ approx normal with mean n*mu, sd sqrt(n)*sd (fat tails via t5)
        tdraw = rng.standard_t(5, p.n_paths) / np.sqrt(5 / 3)
        r_sum = n * p.expectancy_r + np.sqrt(n) * p.r_sd * tdraw
        can_trade = alive & (eq > max(p.ruin_floor, p.min_lot_risk_floor))
        pnl = np.where(can_trade, eq * p.risk_pct / 100 * r_sum, 0.0)
        eq = eq + pnl
        trading_pnl += pnl
        eq -= p.monthly_costs
        costs_paid += p.monthly_costs
        eq += p.monthly_contribution
        deposits += p.monthly_contribution
        hwm = np.maximum(hwm, eq)
        wd = np.where(eq >= hwm, eq * p.monthly_withdrawal_pct_above_hwm / 100, 0.0)
        eq -= wd
        withdrawn += wd
        month_dd = np.maximum(month_dd, 1 - eq / np.maximum(hwm, 1e-9))
        alive &= eq > p.ruin_floor
        eq = np.maximum(eq, 0.0)
        paths[m + 1] = eq

    def q(x):
        return {k: float(np.quantile(x, v)) for k, v in (("p05", .05), ("p25", .25), ("median", .5), ("p75", .75), ("p95", .95))}

    return {
        "inputs": p.__dict__,
        "final_equity": q(eq),
        "total_deposits": float(deposits.mean()),
        "trading_pnl": q(trading_pnl),
        "costs_paid": float(costs_paid.mean()),
        "withdrawn": q(withdrawn),
        "max_drawdown": q(month_dd),
        "p_below_start_plus_deposits": float(np.mean(eq + withdrawn < deposits)),
        "p_exhausted": float(np.mean(~alive)),
        "paths_quantiles": {k: np.quantile(paths, v, axis=1).round(2).tolist() for k, v in
                            (("p05", .05), ("median", .5), ("p95", .95))},
        "label": "ILLUSTRATIVE - assumed returns, not a forecast",
    }


def min_account_for_min_lot(stop_pips: float, pip_value_per_lot: float = 10.0, risk_pct: float = 0.5,
                            min_lot: float = 0.01, commission_per_lot: float = 5.0) -> float:
    """Smallest account where 0.01 lot on `stop_pips` stays within `risk_pct`."""
    loss = min_lot * (stop_pips * pip_value_per_lot + commission_per_lot)
    return loss / (risk_pct / 100)
