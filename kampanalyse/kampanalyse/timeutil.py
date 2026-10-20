"""Tid og tidssoner. All lagring i UTC; all visning i Europe/Oslo."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")

_MONTHS = ["jan.", "feb.", "mars", "apr.", "mai", "juni", "juli", "aug.", "sep.", "okt.", "nov.", "des."]
_DAYS = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]


class Clock:
    """Injiserbar klokke slik at planlegging kan testes (inkl. sommertid)."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    def __init__(self, at: datetime):
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, **kw) -> None:
        self.at = self.at + timedelta(**kw)


def utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naiv datetime er ikke tillatt")
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    return utc(dt).isoformat(timespec="seconds")


def from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def local(dt: datetime) -> datetime:
    return utc(dt).astimezone(OSLO)


def local_date(dt: datetime) -> date:
    return local(dt).date()


def local_at(d: date, t: time) -> datetime:
    """Lokal veggklokketid i Oslo for gitt dato -> UTC. Håndterer sommertid via zoneinfo."""
    return datetime.combine(d, t, tzinfo=OSLO).astimezone(timezone.utc)


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start = local_at(d, time(0, 0))
    end = local_at(d + timedelta(days=1), time(0, 0))
    return start, end


def hm(dt: datetime) -> str:
    return local(dt).strftime("%H:%M")


def nice_date(d: date) -> str:
    return f"{_DAYS[d.weekday()]} {d.day}. {_MONTHS[d.month - 1]} {d.year}"


def stamp(dt: datetime) -> str:
    l = local(dt)
    return f"{l.day}.{l.month:02d} kl. {l.strftime('%H:%M')}"
