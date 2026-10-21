"""Data audit: quality reports for every series + cross-vendor agreement checks.

Writes research/data_audit.json and prints a summary. Usage: python scripts/data_audit.py
"""
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from fxsignal.data import loaders as L
from fxsignal.data.quality import quality_report
from fxsignal.data.resample import resample

OUT = Path(__file__).resolve().parents[1] / "research" / "data_audit.json"


def compare(a: pd.DataFrame, b: pd.DataFrame, pip: float, label: str) -> dict:
    j = a[["close"]].join(b[["close"]], how="inner", lsuffix="_a", rsuffix="_b")
    d = (j.close_a - j.close_b) / pip
    # Also test +/- 1h shifts: a correct timezone should minimise the disagreement.
    shifts = {}
    for h in (-1, 0, 1):
        bb = b.copy(); bb.index = bb.index + pd.Timedelta(hours=h)
        jj = a[["close"]].join(bb[["close"]], how="inner", lsuffix="_a", rsuffix="_b")
        shifts[h] = float(((jj.close_a - jj.close_b).abs() / pip).median())
    return {"pair": label, "overlap_bars": int(len(j)), "median_abs_diff_pips": float(d.abs().median()),
            "p99_abs_diff_pips": float(d.abs().quantile(0.99)), "mean_diff_pips": float(d.mean()),
            "median_abs_diff_by_hour_shift": shifts}


def main():
    res = {"quality": [], "cross_vendor": []}
    for s in L.available_ejtrader_symbols():
        for tf, m in (("m15", 15), ("h1", 60)):
            df = L.load_ejtrader(s, tf)
            res["quality"].append(asdict(quality_report(df, "ejtrader", m, s)))
    m1 = {}
    for s in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD"]:
        m1[("dukascopy", s)] = L.load_dukascopy_m1(s)
        m1[("oanda", s)] = L.load_oanda_m1(s)
    m1[("oanda", "XAUUSD")] = L.load_oanda_m1("XAUUSD")
    m1[("histdata", "EURUSD")] = L.load_histdata_m1("EURUSD")
    for (src, s), df in m1.items():
        res["quality"].append(asdict(quality_report(df, src, 1, s)))

    pip = {"XAUUSD": 0.01}
    h1 = {k: resample(v, "H1") for k, v in m1.items()}
    for s in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD"]:
        ej = L.load_ejtrader(s, "h1")
        p = pip.get(s, 0.0001)
        res["cross_vendor"].append(compare(ej, h1[("dukascopy", s)], p, f"{s} ejtrader vs dukascopy H1"))
        res["cross_vendor"].append(compare(ej, h1[("oanda", s)], p, f"{s} ejtrader vs oanda H1"))
        res["cross_vendor"].append(compare(h1[("dukascopy", s)], h1[("oanda", s)], p, f"{s} dukascopy vs oanda H1"))
    res["cross_vendor"].append(compare(L.load_ejtrader("EURUSD", "h1"), h1[("histdata", "EURUSD")], 0.0001,
                                       "EURUSD ejtrader vs histdata H1"))
    res["cross_vendor"].append(compare(h1[("dukascopy", "EURUSD")], h1[("histdata", "EURUSD")], 0.0001,
                                       "EURUSD dukascopy vs histdata H1"))
    res["cross_vendor"].append(compare(L.load_ejtrader("XAUUSD", "h1"), h1[("oanda", "XAUUSD")], 0.01,
                                       "XAUUSD ejtrader vs oanda H1 (pips = cents)"))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    q = pd.DataFrame(res["quality"])[["source", "symbol", "tf", "first", "last", "rows", "duplicates",
                                       "ohlc_violations", "intraweek_gaps", "longest_intraweek_gap_min",
                                       "flat_runs", "spikes", "coverage_pct"]]
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(q.to_string(index=False))
    print(pd.DataFrame(res["cross_vendor"]).to_string(index=False))


if __name__ == "__main__":
    main()
