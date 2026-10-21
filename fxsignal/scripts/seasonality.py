"""Descriptive: mean USD return (sign-adjusted, pips) by London hour, per split. Not a strategy."""
import numpy as np
import pandas as pd

from fxsignal.data import loaders as L
from fxsignal.research.runner import SPLITS

rows = []
for sym in ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD", "USDCHF"]:
    h1 = L.load_ejtrader(sym, "h1")
    pip = 0.01 if sym.endswith("JPY") else 0.0001
    r = (h1["close"] - h1["open"]) / pip * (1 if sym.startswith("USD") else -1)  # + = USD up
    hr = h1.index.tz_convert("Europe/London").hour
    for split in ("dev", "val"):
        a, b = (pd.Timestamp(x, tz="UTC") for x in SPLITS[split])
        m = (h1.index >= a) & (h1.index < b)
        g = r[m].groupby(hr[m])
        rows.append(pd.DataFrame({"sym": sym, "split": split, "hour": g.mean().index, "mean_pips": g.mean().values,
                                  "t": (g.mean() / g.std() * np.sqrt(g.count())).values}))
df = pd.concat(rows)
piv = df.pivot_table(index="hour", columns="split", values="mean_pips", aggfunc="mean").round(3)
tpiv = df.pivot_table(index="hour", columns="split", values="t", aggfunc="mean").round(2)
print("Mean USD move per London hour (pips, averaged over 6 USD pairs) and mean t-stat")
print(pd.concat([piv, tpiv.add_prefix("t_")], axis=1).to_string())
print("For scale: modelled round-trip spread in liquid hours is ~0.4-0.7 pips plus ~0.5 pip commission.")
