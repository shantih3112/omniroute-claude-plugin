"""Gate R for XAUUSD, evaluated separately from FX (same pre-declared grids, dev split)."""
import pandas as pd
from fxsignal.research.runner import run
from fxsignal.strategies.library import GRIDS

rows = []
for fam, cfgs in GRIDS.items():
    if fam in ("usd_fix", "round_break"):
        continue  # FX-specific hypotheses
    for cfg in cfgs:
        tr, s = run(fam, cfg, ["XAUUSD"], "dev", tag="gateR-xau")
        rows.append(dict(family=fam, cfg=cfg, n=s.get("filled"), exp_r=s.get("expectancy_r"),
                         gross_r=s.get("expectancy_gross_r"), t=s.get("t_stat_weekly"), pf=s.get("profit_factor")))
for seed in range(3):
    tr, s = run("random", dict(seed=seed), ["XAUUSD"], "dev", tag="gateR-xau")
    rows.append(dict(family="random", cfg=dict(seed=seed), n=s.get("filled"), exp_r=s.get("expectancy_r"),
                     gross_r=s.get("expectancy_gross_r"), t=s.get("t_stat_weekly"), pf=s.get("profit_factor")))
pd.set_option("display.width", 200)
print(pd.DataFrame(rows).round(3).to_string())
