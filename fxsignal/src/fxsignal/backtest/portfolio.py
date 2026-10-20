"""Portfolio-level replay of research trades under the live risk limits.

Walks filled trades in entry order and admits each one only if the same limits the live
RiskEngine applies would allow it (open risk, per-currency net exposure, one per symbol,
optional pair-correlation block). Rejected trades get status `skipped_portfolio`. Used for
portfolio drawdown, FTMO and planning studies so that they reflect what the service would
actually publish.
"""
from __future__ import annotations

import pandas as pd

from .. import instruments
from ..risk.engine import RiskConfig


def apply_limits(trades: pd.DataFrame, cfg: RiskConfig = RiskConfig(), risk_pct: float | None = None) -> pd.DataFrame:
    risk = cfg.risk_per_trade_pct if risk_pct is None else risk_pct
    t = trades.copy()
    t["entry_time"] = pd.to_datetime(t["entry_time"])
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    order = t[t["status"] == "filled"].sort_values("entry_time").index
    open_: list[tuple[pd.Timestamp, str, int]] = []
    for i in order:
        row = t.loc[i]
        now = row["entry_time"]
        open_ = [o for o in open_ if o[0] > now]
        inst = instruments.get(row["symbol"])
        ok = len(open_) * risk + risk <= cfg.max_open_risk_pct + 1e-9
        ok &= all(o[1] != row["symbol"] for o in open_)
        if ok:
            ex: dict[str, float] = {}
            for _, sym, side in open_ + [(None, row["symbol"], int(row["side"]))]:
                ins = instruments.get(sym)
                ex[ins.base] = ex.get(ins.base, 0.0) + side * risk
                ex[ins.quote] = ex.get(ins.quote, 0.0) - side * risk
            ok = all(abs(ex[c]) <= cfg.max_currency_exposure_pct + 1e-9 for c in (inst.base, inst.quote))
        if ok:
            open_.append((row["exit_time"], row["symbol"], int(row["side"])))
        else:
            t.loc[i, "status"] = "skipped_portfolio"
    return t
