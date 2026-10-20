"""Research runner + append-only experiment registry.

Every evaluated configuration is appended to research/registry.jsonl with the git commit, the
scorecard version, the data fingerprint, the split and the summary metrics -- including the
failures. Gate M counts these rows when deflating Sharpe ratios.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .. import instruments
from ..backtest import metrics as M
from ..backtest.engine import BASE, CostScenario, ExecSeries, simulate
from ..data import loaders as L
from ..data.resample import resample
from ..strategies.library import REGISTRY

ROOT = Path(__file__).resolve().parents[3]
REG = ROOT / "research" / "registry.jsonl"
SCORECARD_VERSION = "v1"

SPLITS = {
    "dev": ("2012-11-16", "2018-01-01"),
    "val": ("2018-01-01", "2021-01-01"),
    "holdA": ("2021-01-01", "2022-03-05"),
    "holdB": ("2022-03-07", "2026-10-03"),
}
EJ_FX = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF"]
HOLDB_FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD"]


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


@lru_cache(maxsize=64)
def series(symbol: str, source: str) -> dict:
    """Signal-timeframe inputs and the execution series for a symbol/source."""
    if source == "ejtrader":
        h1, m15 = L.load_ejtrader(symbol, "h1"), L.load_ejtrader(symbol, "m15")
        return {"H1": h1, "M15": m15, "exec": ExecSeries(m15, 15), "exec_tf": 15}
    if source in ("dukascopy", "oanda"):
        m1 = L.load_dukascopy_m1(symbol) if source == "dukascopy" else L.load_oanda_m1(symbol)
        return {"H1": resample(m1, "H1"), "M15": resample(m1, "M15"), "exec": ExecSeries(m1, 1), "exec_tf": 1}
    raise ValueError(source)


def fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(str((len(df), str(df.index[0]), str(df.index[-1]), float(df["close"].sum()))).encode())
    return h.hexdigest()[:12]


def run(name: str, cfg: dict, symbols: list[str], split: str, source: str = "ejtrader",
        cost: CostScenario = BASE, delay_min: float | None = None, max_dev_r: float = 0.25,
        log: bool = True, tag: str = "", filt=None) -> tuple[pd.DataFrame, dict]:
    """Run one configuration over symbols for one split. Returns (trades, summary)."""
    a, b = (pd.Timestamp(x, tz="UTC") for x in SPLITS[split])
    parts = []
    fps = {}
    for sym in symbols:
        d = series(sym, source)
        strat = REGISTRY[name](**cfg)
        inp = d[strat.signal_tf]
        inp.attrs["symbol"] = sym
        sig = strat.generate(inp)
        sig = sig[(sig["time"] >= a) & (sig["time"] < b)].reset_index(drop=True)
        if filt is not None:
            sig = filt(sig, sym, d).reset_index(drop=True)
        dl = d["exec_tf"] if delay_min is None else delay_min
        tr = simulate(sig, d["exec"], instruments.get(sym), cost, dl, max_dev_r, trail=strat.trail)
        tr["symbol"] = sym
        if len(sig):
            tr["regime"] = sig["regime"].to_numpy()[: len(tr)]
        parts.append(tr)
        fps[sym] = fingerprint(d["H1"])
    trades = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    summ = M.summarize(trades) if len(trades) else {"signals": 0, "filled": 0}
    if log:
        sid = REGISTRY[name](**cfg).id
        rec = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), git=git_sha(),
                   scorecard=SCORECARD_VERSION, strategy=sid, family=name, split=split, source=source,
                   symbols=symbols, cost=cost.name, delay_min=dl if symbols else None, max_dev_r=max_dev_r,
                   tag=tag, data=fps, summary=_jsonable(summ))
        REG.parent.mkdir(exist_ok=True)
        with REG.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    return trades, summ


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    return x


def registry_rows(family: str | None = None) -> list[dict]:
    if not REG.exists():
        return []
    rows = [json.loads(l) for l in REG.read_text().splitlines() if l.strip()]
    return [r for r in rows if family is None or r["family"] == family]
