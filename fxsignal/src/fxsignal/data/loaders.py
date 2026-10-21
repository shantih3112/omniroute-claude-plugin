"""Historical data loaders for the vendor mirrors available to this project.

Every loader returns a DataFrame indexed by the UTC bar OPEN time (tz-aware), with float
columns open/high/low/close (BID prices) and `tick_volume` (a broker/vendor tick-count proxy,
NOT traded volume -- spot FX has no consolidated volume).

Sources (see docs/DATA.md for provenance and caveats):
  ejtrader  : MT5-style export, 11 FX pairs + XAUUSD, M15/M30/H1/H4/D1, 2012-11 .. 2022-03.
              Server clock = EET/EEST with EU daylight-saving rules (UTC+2 winter, UTC+3
              summer); verified against Dukascopy, including the March/October weeks when
              US and EU DST differ. Prices stored as integers scaled by 10**digits.
              Its H4/D1 files follow the server clock, so H4/D1 are rebuilt from H1 instead.
  dukascopy : M1 BID, UTC, EURUSD/GBPUSD/AUDUSD/USDCAD, 2020-01 .. 2026-10.
  oanda     : M1 BID, UTC, same pairs + XAUUSD, 2019/2020 .. 2026-10.
  histdata  : M1 BID, EURUSD 2010 .. 2025. HistData.com documents fixed EST, but this mirror's
              timestamps match Dukascopy only when read as America/New_York local time WITH
              daylight saving (verified month by month), so that is how they are read.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ..timeutil import NY

DATA_DIR = Path(os.environ.get("FXSIGNAL_DATA", Path(__file__).resolve().parents[3] / "data"))
RAW = DATA_DIR / "raw"
CACHE = DATA_DIR / "cache"

COLS = ["open", "high", "low", "close", "tick_volume"]
EJ_SCALE = {"XAUUSD": 100.0}  # others: 1e5, JPY pairs 1e3


def _ej_scale(symbol: str) -> float:
    if symbol in EJ_SCALE:
        return EJ_SCALE[symbol]
    return 1e3 if symbol.endswith("JPY") else 1e5


def _cached(name: str, builder) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    df = builder()
    df.to_parquet(p)
    return df


EJ_SERVER_TZ = "Europe/Helsinki"  # EET/EEST, EU DST rules


def server_eet_to_utc(naive: pd.Series) -> pd.DatetimeIndex:
    loc = pd.DatetimeIndex(naive).tz_localize(EJ_SERVER_TZ, ambiguous="NaT", nonexistent="NaT")
    return loc.tz_convert("UTC")


def load_ejtrader(symbol: str, tf: str) -> pd.DataFrame:
    """tf in {m15, m30, h1}. Do not use the vendor h4/d1 files (server-clock aligned)."""
    symbol, tf = symbol.upper(), tf.lower()

    def build():
        f = RAW / "ejtrader" / symbol / f"{symbol}{tf}.csv"
        raw = pd.read_csv(f)
        idx = server_eet_to_utc(pd.to_datetime(raw["Date"]))
        s = _ej_scale(symbol)
        df = pd.DataFrame(
            {c: raw[c].to_numpy(float) / s for c in ["open", "high", "low", "close"]}, index=idx
        )
        df["tick_volume"] = raw["tick_volume"].to_numpy(float)
        df = df[~df.index.isna()]
        df.index.name = "time"
        return _finalize(df, symbol)

    return _cached(f"ejtrader2_{symbol}_{tf}", build)


def _load_m1_gz(pattern: str, symbol: str) -> pd.DataFrame:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(pattern)
    parts = []
    for f in files:
        raw = pd.read_csv(f)
        idx = pd.DatetimeIndex(pd.to_datetime(raw["time_utc"])).tz_localize("UTC")
        df = pd.DataFrame({c: raw[c].to_numpy(float) for c in ["open", "high", "low", "close"]}, index=idx)
        df["tick_volume"] = raw["volume"].to_numpy(float)
        parts.append(df)
    df = pd.concat(parts)
    df.index.name = "time"
    return _finalize(df, symbol)


def load_dukascopy_m1(symbol: str) -> pd.DataFrame:
    symbol = symbol.upper()
    return _cached(f"dukascopy_{symbol}_m1",
                   lambda: _load_m1_gz(str(RAW / "dukascopy" / f"{symbol}_M1_BID_*_UTC.csv.gz"), symbol))


def load_oanda_m1(symbol: str) -> pd.DataFrame:
    symbol = symbol.upper()
    return _cached(f"oanda_{symbol}_m1",
                   lambda: _load_m1_gz(str(RAW / "oanda" / f"{symbol}_OANDA_M1_BID_*_UTC.csv.gz"), symbol))


def load_histdata_m1(symbol: str = "EURUSD") -> pd.DataFrame:
    symbol = symbol.upper()

    def build():
        parts = []
        for f in sorted(glob.glob(str(RAW / "histdata_eurusd_m1" / f"DAT_ASCII_{symbol}_M1_*.csv"))):
            raw = pd.read_csv(f, sep=";", header=None,
                              names=["t", "open", "high", "low", "close", "v"])
            local = pd.to_datetime(raw["t"], format="%Y%m%d %H%M%S")
            idx = pd.DatetimeIndex(local).tz_localize(NY, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
            df = pd.DataFrame({c: raw[c].to_numpy(float) for c in ["open", "high", "low", "close"]}, index=idx)
            df["tick_volume"] = np.nan  # HistData M1 ASCII carries no usable volume
            parts.append(df)
        df = pd.concat(parts)
        df = df[~df.index.isna()]
        df.index.name = "time"
        return _finalize(df, symbol)

    return _cached(f"histdata2_{symbol}_m1", build)


def _finalize(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Sort and de-duplicate (keep first), never fabricate rows."""
    df = df.sort_index(kind="stable")
    df = df[~df.index.duplicated(keep="first")]
    df.attrs["symbol"] = symbol
    return df[COLS]


def available_ejtrader_symbols() -> list[str]:
    d = RAW / "ejtrader"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []
