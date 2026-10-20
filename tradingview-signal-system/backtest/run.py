"""Run the ported logic on real public OHLC datasets with chronological splits.

Usage: python3 -I backtest/run.py <data_dir>
Splits per series: first 60% of bars = development, next 20% = validation,
final 20% = test. Indicators run causally over the whole series; each trade is
assigned to the split containing its signal bar. Parameters were fixed before
any run (Pine defaults); nothing was optimised on these data.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from engine import Cfg, metrics, run  # noqa: E402

D = Path(sys.argv[1])


def load(name):
    if name == "BTC":
        df = pd.read_csv(D / "BTC.csv")
        df.index = pd.to_datetime(df["Timestamp"], unit="s")
        df = df.rename(columns={"Volume_BTC": "Volume"})[["Open", "High", "Low", "Close", "Volume"]]
    elif name == "AAPL":
        df = pd.read_csv(D / "AAPL.csv", parse_dates=["Date"], index_col="Date")
        df = df.rename(columns=lambda c: c.replace("AAPL.", ""))[["Open", "High", "Low", "Close", "Volume"]]
    else:
        df = pd.read_csv(D / f"{name}.csv", index_col=0, parse_dates=True)
    ohlc = df[["Open", "High", "Low", "Close"]]
    # BTC file marks missing hours with a 1.7e308 sentinel: drop them.
    df = df[(ohlc < 1e7).all(axis=1) & (df["High"] >= df["Low"]) & (df["Close"] > 0)].sort_index()
    return df[~df.index.duplicated()]


def resample(df, rule):
    return df.resample(rule, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()


# Costs per side (fraction of price): commission + slippage + half spread.
STOCK, FX, CRYPTO = 0.0005 + 0.0002, 0.00007, 0.0010 + 0.0005
btc = load("BTC")
eur = load("EURUSD")
SERIES = [
    ("GOOG", "D", load("GOOG"), Cfg("Stock", "W-MON", STOCK, short_ok=False)),
    ("AAPL", "D", load("AAPL"), Cfg("Stock", "W-MON", STOCK, short_ok=False)),
    ("EURUSD", "1h", eur, Cfg("Forex", "4h", FX, leverage=20)),
    ("EURUSD", "4h", resample(eur, "4h"), Cfg("Forex", "1D", FX, leverage=20)),
    ("BTCUSD", "1h", btc, Cfg("Crypto", "4h", CRYPTO)),
    ("BTCUSD", "4h", resample(btc, "4h"), Cfg("Crypto", "1D", CRYPTO)),
    ("BTCUSD", "D", resample(btc, "1D"), Cfg("Crypto", "W-MON", CRYPTO)),
]
SPLITS = [("dev", 0.0, 0.6), ("val", 0.6, 0.8), ("test", 0.8, 1.0)]


def variants(cfg):
    yield "FULL", cfg
    # Defaults chosen from the DEVELOPMENT split only (sweep & range-reversion off)
    ab = {"TP": True, "BO": True, "MR": False, "SW": False}
    yield "DEFAULT_AB", Cfg(**{**cfg.__dict__, "use": ab})
    yield "DEFAULT_AB_2xCOST", Cfg(**{**cfg.__dict__, "use": ab, "cost_side": 2 * cfg.cost_side})
    yield "BASELINE", Cfg(**{**cfg.__dict__, "baseline": True})
    for s in ("TP", "BO", "MR", "SW"):
        only = {k: k == s for k in ("TP", "BO", "MR", "SW")}
        yield f"only_{s}", Cfg(**{**cfg.__dict__, "use": only})


rows = []
for sym, tf, df, cfg in SERIES:
    n = len(df)
    for vname, vcfg in variants(cfg):
        trades, aux = run(df, vcfg)
        for split, a, b in SPLITS:
            lo, hi = int(a * n), int(b * n)
            t = trades[(trades["sig_bar"] >= lo) & (trades["sig_bar"] < hi)] if len(trades) else trades
            m = metrics(t, hi - lo, int(aux["in_trade"][lo:hi].sum()), vcfg)
            bh = 100 * (df["Close"].iloc[hi - 1] / df["Close"].iloc[lo] - 1)
            reg = aux["regime"][lo:hi]
            rows.append(dict(symbol=sym, tf=tf, variant=vname, split=split,
                             start=df.index[lo].date(), end=df.index[hi - 1].date(), bars=hi - lo,
                             buyhold_pct=round(bh, 1),
                             reg_up=round(100 * np.mean(reg == 1)), reg_dn=round(100 * np.mean(reg == -1)),
                             reg_range=round(100 * np.mean(reg == 0)), **m))
        print(f"done {sym} {tf} {vname}: {len(trades)} trades", file=sys.stderr)

res = pd.DataFrame(rows)
out = Path(__file__).parent / "results.csv"
res.to_csv(out, index=False)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 500)
cols = ["symbol", "tf", "variant", "split", "start", "end", "trades", "win_rate", "avg_win_R", "avg_loss_R",
        "expectancy_R", "pf", "total_R", "ret_pct", "max_dd_pct", "max_loss_streak", "exposure", "buyhold_pct"]
print(res[cols].to_string(index=False))
