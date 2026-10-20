"""Time conventions.

* Everything internal is timezone-aware UTC.
* The forex trading day ends at 17:00 America/New_York ("NY close"). Shifting NY local time
  by +7 hours gives "fx time", in which every trading day starts at 00:00 and the week starts
  on Monday 00:00 regardless of daylight saving. D1 and H4 bars are built on fx time.
* User-facing times are shown in Europe/Oslo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
OSLO = ZoneInfo("Europe/Oslo")
PRAGUE = ZoneInfo("Europe/Prague")
FX_SHIFT = pd.Timedelta(hours=7)


def to_fx_time(ts_utc: pd.DatetimeIndex | pd.Series) -> pd.DatetimeIndex:
    """UTC -> naive 'fx time' (NY local + 7h)."""
    idx = pd.DatetimeIndex(ts_utc)
    return idx.tz_convert(NY).tz_localize(None) + FX_SHIFT


def from_fx_time(naive: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Naive fx time -> UTC. Weekend-only ambiguous/nonexistent times are pushed forward."""
    ny = pd.DatetimeIndex(naive) - FX_SHIFT
    return ny.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert(UTC)


def fx_day(ts: datetime) -> pd.Timestamp:
    """The trading-day label (date) that a UTC timestamp belongs to."""
    t = pd.Timestamp(ts).tz_convert(NY).tz_localize(None) + FX_SHIFT
    return t.normalize()


def market_open(ts: datetime) -> bool:
    """Spot FX is open from Sunday 17:00 to Friday 17:00 New York time.

    Holidays (Dec 25, Jan 1) are treated as open but illiquid; liquidity rules handle them.
    """
    ny = pd.Timestamp(ts).tz_convert(NY)
    wd, h = ny.weekday(), ny.hour
    if wd == 5:
        return False
    if wd == 4 and h >= 17:
        return False
    if wd == 6 and h < 17:
        return False
    return True


def is_illiquid_holiday(ts: datetime) -> bool:
    ny = pd.Timestamp(ts).tz_convert(NY)
    return (ny.month, ny.day) in {(12, 24), (12, 25), (12, 26), (12, 31), (1, 1)}


def fmt_oslo(ts: datetime | None) -> str:
    if ts is None:
        return "-"
    return pd.Timestamp(ts).tz_convert(OSLO).strftime("%Y-%m-%d %H:%M %Z")


def utcnow() -> datetime:
    return datetime.now(UTC)


def floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


def open_hours_between(t0: datetime, t1: datetime, skip_holidays: bool = True) -> float:
    """Hours of regular FX market time strictly inside (t0, t1), sampled every 15 minutes.

    With `skip_holidays`, Dec 24-26 and Dec 31-Jan 2 do not count (many venues close).
    """
    a, b = pd.Timestamp(t0), pd.Timestamp(t1)
    if b - a <= pd.Timedelta(minutes=15):
        return 0.0
    grid = pd.date_range(a + pd.Timedelta(minutes=15), b - pd.Timedelta(minutes=1), freq="15min")
    ny = grid.tz_convert(NY)
    wd, h = ny.dayofweek, ny.hour
    open_ = ~((wd == 5) | ((wd == 4) & (h >= 17)) | ((wd == 6) & (h < 17)))
    if skip_holidays:
        md = list(zip(ny.month, ny.day))
        hol = pd.Index(md).isin([(12, 24), (12, 25), (12, 26), (12, 31), (1, 1), (1, 2)])
        open_ = open_ & ~hol
    return float(open_.sum()) / 4.0
