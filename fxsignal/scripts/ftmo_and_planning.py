"""FTMO pass-rate study + illustrative capital planning. Writes research/ftmo_planning.json.

Part 1 uses the best-scoring (still failing) research candidates on the development split.
Part 2 uses HYPOTHETICAL trade streams with an assumed edge, to show what edge would be needed;
these are not results of any strategy.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fxsignal.backtest.portfolio import apply_limits
from fxsignal.risk.engine import RiskConfig
from fxsignal.research.planner import PlanInputs, min_account_for_min_lot, simulate
from fxsignal.research.runner import EJ_FX, run
from fxsignal.risk.ftmo import FtmoProfile, pass_rate_study

ROOT = Path(__file__).resolve().parents[1]
prof = FtmoProfile.load(ROOT / "config/ftmo/2step_standard_phase1.yaml")
out = {"profile": prof.name, "profile_version": prof.version, "verified": prof.verified,
       "compliance": prof.challenge_use_allowed()[1], "research_candidates": {}, "hypothetical": {}}

for fam, cfg in [("trend_pullback", dict(trend_ema=50, rsi_lo=35, rr=2.0)), ("tsmom_weekly", dict(lookback_d=120)),
                 ("random", dict(seed=0))]:
    tr, s = run(fam, cfg, EJ_FX, "dev", log=False)
    for risk in (0.5, 1.0):
        # same portfolio limits as the live risk engine (2% open risk, 1% per currency at 0.5%)
        lim = apply_limits(tr, RiskConfig(risk_per_trade_pct=risk, max_open_risk_pct=4 * risk,
                                          max_currency_exposure_pct=2 * risk), risk)
        out["research_candidates"][f"{fam} risk {risk}%"] = dict(
            pass_rate_study(lim, prof, risk, n_starts=60, max_days=120),
            trades_after_limits=int((lim.status == "filled").sum()), trades_before=int((tr.status == "filled").sum()))


def synthetic_trades(exp_r, win=0.4, n_per_day=1.0, days=1500, seed=0):
    """Hypothetical i.i.d. trades: wins of size a, losses of -1 (with MAE -1), chosen so mean = exp_r."""
    rng = np.random.default_rng(seed)
    a = (exp_r + (1 - win)) / win
    rows = []
    t = pd.Timestamp("2015-01-05 08:00", tz="UTC")
    for d in range(days):
        day = t + pd.Timedelta(days=d)
        if day.dayofweek >= 5:
            continue
        for k in range(rng.poisson(n_per_day)):
            w = rng.random() < win
            r = a if w else -1.0
            mae = -rng.uniform(0.2, 0.9) if w else -1.0
            rows.append(dict(entry_time=day + pd.Timedelta(hours=k), exit_time=day + pd.Timedelta(hours=k + 4),
                             r_net=r, mae_r=mae, status="filled"))
    return pd.DataFrame(rows)


for exp in (0.0, 0.1, 0.2, 0.3):
    st = synthetic_trades(exp)
    for risk in (0.5, 1.0):
        out["hypothetical"][f"assumed {exp:+.1f}R/trade, 40% win, ~1 trade/day, risk {risk}%"] = \
            pass_rate_study(st, prof, risk, n_starts=80, max_days=120)

plans = {}
for label, exp in (("no edge (what the research found)", 0.0), ("assumed +0.1R", 0.1), ("assumed +0.2R", 0.2)):
    res = simulate(PlanInputs(start_capital=1000, monthly_contribution=100, monthly_costs=15, years=10,
                              trades_per_month=20, risk_pct=0.5, expectancy_r=exp))
    res.pop("paths_quantiles")
    plans[label] = res
out["planning"] = plans
out["min_account_for_0.01_lot"] = {f"{s}-pip stop at 0.5%": round(min_account_for_min_lot(s), 0) for s in (10, 20, 40, 80)}
(ROOT / "research").mkdir(exist_ok=True)
(ROOT / "research" / "ftmo_planning.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps({k: v for k, v in out.items() if k != "planning"}, indent=1, default=str))
for k, v in plans.items():
    print(k, "final equity", {a: round(b) for a, b in v["final_equity"].items()}, "deposits", round(v["total_deposits"]),
          "P(below deposits)", round(v["p_below_start_plus_deposits"], 3), "P(exhausted)", round(v["p_exhausted"], 3))
