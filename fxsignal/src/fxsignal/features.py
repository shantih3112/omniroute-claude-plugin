"""Causal indicator library.

Every function returns a series whose value at bar t uses bars <= t only (the value is known at
bar t's CLOSE). Anything that needs "the level before this bar" (e.g. a breakout threshold) is
shifted explicitly by the caller-facing helper (`prior_*`). Truncation-invariance tests in
tests/test_no_lookahead.py check this for every function used by a strategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift(1)
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ATR."""
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(x: pd.Series, n: int = 14) -> pd.Series:
    d = x.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l = df["high"], df["low"]
    upm, dnm = h.diff(), -l.diff()
    pdm = np.where((upm > dnm) & (upm > 0), upm, 0.0)
    ndm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    ndi = 100 * pd.Series(ndm, index=df.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def prior_high(df: pd.DataFrame, n: int) -> pd.Series:
    """Highest high of the n bars BEFORE bar t (excludes bar t)."""
    return df["high"].rolling(n, min_periods=n).max().shift(1)


def prior_low(df: pd.DataFrame, n: int) -> pd.Series:
    return df["low"].rolling(n, min_periods=n).min().shift(1)


def bollinger(x: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    m = sma(x, n)
    s = x.rolling(n, min_periods=n).std(ddof=0)
    return m - k * s, m, m + k * s


def rolling_pct_rank(x: pd.Series, n: int) -> pd.Series:
    """Percentile (0..1) of x[t] within x[t-n+1..t]. Causal."""
    return x.rolling(n, min_periods=n).rank(pct=True)


def efficiency_ratio(x: pd.Series, n: int) -> pd.Series:
    """Kaufman efficiency ratio: |net move| / path length over n bars (trendiness, 0..1)."""
    net = (x - x.shift(n)).abs()
    path = x.diff().abs().rolling(n, min_periods=n).sum()
    return net / path.replace(0, np.nan)


def regime_label(adx_v: pd.Series, atr_pct: pd.Series) -> pd.Series:
    """Coarse causal regime: trend/range x high/normal volatility. Used for reporting & filters."""
    trend = np.where(adx_v >= 25, "trend", np.where(adx_v <= 18, "range", "mixed"))
    vol = np.where(atr_pct >= 0.8, "hivol", np.where(atr_pct <= 0.2, "lovol", "normvol"))
    out = pd.Series([f"{a}/{b}" for a, b in zip(trend, vol)], index=adx_v.index)
    out[adx_v.isna() | atr_pct.isna()] = "unknown"
    return out
