"""Data-quality checks for bar series (historical and live).

The live scanner uses `check_live_bar` to decide whether a newly completed bar may be used;
research uses `quality_report` to describe a whole series. Nothing here repairs data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..timeutil import market_open


@dataclass
class QualityReport:
    symbol: str
    source: str
    tf: str
    first: str
    last: str
    rows: int
    duplicates: int
    out_of_order: int
    ohlc_violations: int
    nonpositive: int
    intraweek_gaps: int
    longest_intraweek_gap_min: float
    flat_runs: int
    spikes: int
    expected_rows_estimate: int
    coverage_pct: float
    notes: list[str] = field(default_factory=list)


def quality_report(df: pd.DataFrame, source: str, tf_minutes: int, symbol: str | None = None) -> QualityReport:
    symbol = symbol or df.attrs.get("symbol", "?")
    idx = df.index
    dups = int(idx.duplicated().sum())
    ooo = int((np.diff(idx.asi8) < 0).sum())
    o, h, l, c = (df[k].to_numpy() for k in ["open", "high", "low", "close"])
    viol = int(((h < np.maximum(o, c) - 1e-12) | (l > np.minimum(o, c) + 1e-12) | (h < l)).sum())
    nonpos = int(((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)).sum())

    gaps = np.diff(idx.asi8) / 6e10  # minutes
    starts = idx[:-1]
    # A gap is "intraweek" if the market was open throughout: check the midpoint is in hours.
    big = np.where(gaps > max(4 * tf_minutes, 60))[0]
    intraweek = []
    for i in big:
        mid = starts[i] + pd.Timedelta(minutes=gaps[i] / 2)
        if market_open(mid.to_pydatetime()) and gaps[i] < 60 * 40:
            intraweek.append(gaps[i])
    # Flat runs: >= 30 consecutive bars with zero range (frozen feed symptom).
    rng0 = (h - l) == 0
    runs, cur = 0, 0
    for z in rng0:
        cur = cur + 1 if z else 0
        if cur == 30:
            runs += 1
    # Spikes: |log return| > 12 robust sigmas.
    r = np.diff(np.log(c))
    mad = np.median(np.abs(r - np.median(r))) * 1.4826 or 1e-12
    spikes = int((np.abs(r) > 12 * mad).sum())

    span_days = (idx[-1] - idx[0]).total_seconds() / 86400
    open_minutes = span_days * (5 / 7) * 1440
    expected = int(open_minutes / tf_minutes)
    cov = 100.0 * len(df) / expected if expected else float("nan")
    notes = []
    if source in ("dukascopy", "oanda", "histdata", "ejtrader"):
        notes.append("BID prices only; ask is modelled from the spread assumption.")
    if "tick_volume" in df and df["tick_volume"].isna().all():
        notes.append("No volume field.")
    return QualityReport(symbol, source, f"{tf_minutes}m", str(idx[0]), str(idx[-1]), len(df), dups, ooo, viol,
                         nonpos, len(intraweek), float(max(intraweek) if intraweek else 0.0), runs, spikes,
                         expected, round(cov, 2), notes)


@dataclass
class LiveBarVerdict:
    ok: bool
    reasons: list[str]


def check_live_bar(bar_time_utc: pd.Timestamp, last_bar_time_utc: pd.Timestamp | None, now_utc: pd.Timestamp,
                   o: float, h: float, l: float, c: float, tf_minutes: int = 1,
                   max_staleness_min: float = 3.0, recent_closes: np.ndarray | None = None) -> LiveBarVerdict:
    """Gate a freshly completed live bar. Any failure suppresses signal generation for the symbol."""
    reasons = []
    if last_bar_time_utc is not None:
        if bar_time_utc <= last_bar_time_utc:
            reasons.append("duplicate or out-of-order bar")
    close_time = bar_time_utc + pd.Timedelta(minutes=tf_minutes)
    if close_time > now_utc + pd.Timedelta(seconds=5):
        reasons.append("bar not complete yet (clock skew or provider error)")
    if (now_utc - close_time).total_seconds() / 60 > max_staleness_min:
        reasons.append(f"stale: bar closed {(now_utc - close_time).total_seconds() / 60:.1f} min ago")
    if not (h >= max(o, c) and l <= min(o, c) and min(o, h, l, c) > 0):
        reasons.append("OHLC inconsistent")
    if recent_closes is not None and len(recent_closes) > 30:
        r = np.diff(np.log(recent_closes))
        mad = np.median(np.abs(r - np.median(r))) * 1.4826
        jump = abs(np.log(c / recent_closes[-1]))
        if mad > 0 and jump > 25 * mad:
            reasons.append(f"price jump {jump / mad:.0f} robust sigmas; awaiting confirmation")
    return LiveBarVerdict(not reasons, reasons)
