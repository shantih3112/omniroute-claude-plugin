"""Causal resampling and multi-timeframe alignment.

Bars are labelled by their OPEN time; a bar is only usable after its CLOSE time
(`open + timeframe`). `align_to` attaches higher-timeframe values to lower-timeframe bars using
only higher-timeframe bars that had fully closed at the lower bar's close -- this is the single
place where look-ahead across timeframes could leak, and it is covered by tests.
"""
from __future__ import annotations

import pandas as pd

from ..timeutil import FX_SHIFT, NY

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def tf_delta(tf: str) -> pd.Timedelta:
    return pd.Timedelta(minutes=TF_MINUTES[tf.upper()])


def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample BID OHLC bars to `tf`.

    H4 and D1 are aligned to the New York 17:00 close (fx time) so that D1 has five bars a week
    and H4 boundaries do not move with daylight saving. Intraday TFs <= H1 are UTC aligned.
    Bars with no underlying data are dropped, never forward-filled.
    """
    tf = tf.upper()
    rule = f"{TF_MINUTES[tf]}min"
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    if tf in ("H4", "D1"):
        fx = df.index.tz_convert(NY).tz_localize(None) + FX_SHIFT
        tmp = df.set_axis(fx)
        out = tmp.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
        ny = out.index - FX_SHIFT
        utc = ny.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
        out = out.set_axis(utc)
        out = out[~out.index.isna()]
    else:
        out = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    out.index.name = "time"
    out.attrs = dict(df.attrs, tf=tf)
    return out


def close_times(df: pd.DataFrame, tf: str) -> pd.DatetimeIndex:
    return df.index + tf_delta(tf)


def align_to(ltf: pd.DataFrame, ltf_tf: str, htf_feats: pd.DataFrame, htf_tf: str) -> pd.DataFrame:
    """For each LTF bar, the latest HTF feature row whose bar had CLOSED by the LTF bar close.

    D1/H4 bars in fx time can be shorter around DST shifts or at week end; using the next bar's
    open as the close time would wait over weekends. We use open + nominal timeframe, which is
    conservative for the first H4 bar after a DST change (never early).
    """
    left = pd.DataFrame({"t": close_times(ltf, ltf_tf)}, index=ltf.index)
    right = htf_feats.copy()
    right["t"] = close_times(htf_feats, htf_tf)
    right = right.sort_values("t")
    merged = pd.merge_asof(left.reset_index(), right.reset_index(drop=True), on="t",
                           direction="backward", allow_exact_matches=True)
    merged.index = ltf.index
    return merged.drop(columns=["t", "time"], errors="ignore")
