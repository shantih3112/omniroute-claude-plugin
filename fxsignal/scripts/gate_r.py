"""Gate R: every pre-declared grid config on the development split (all 11 FX pairs, base costs,
default delay = one execution bar). Prints a table; every run is appended to the registry."""
import sys
import time

import pandas as pd

from fxsignal.research.runner import EJ_FX, run
from fxsignal.strategies.library import GRIDS

rows = []
fams = sys.argv[1:] or list(GRIDS) + ["random"]
for fam in fams:
    cfgs = GRIDS.get(fam, [dict(seed=s) for s in range(3)])
    for cfg in cfgs:
        t0 = time.time()
        tr, s = run(fam, cfg, EJ_FX, "dev", tag="gateR-fix2")
        rows.append(dict(family=fam, cfg=cfg, n=s.get("filled"), exp_r=s.get("expectancy_r"),
                         gross_r=s.get("expectancy_gross_r"), t=s.get("t_stat_weekly"), pf=s.get("profit_factor"),
                         win=s.get("win_rate"), mdd=s.get("max_dd_pct"), ci=s.get("expectancy_ci90"),
                         missed=s.get("missed_rate"), secs=round(time.time() - t0)))
        print(rows[-1], flush=True)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(pd.DataFrame(rows).round(3).to_string())
