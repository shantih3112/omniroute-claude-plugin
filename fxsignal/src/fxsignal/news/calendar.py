"""Economic calendar ingestion, event→currency mapping and blackout decisions.

Source used by default: the weekly JSON export behind Forex Factory's calendar
(https://nfs.faireconomy.media/ff_calendar_thisweek.json). It is free, widely used and
UNOFFICIAL: no SLA, no historical archive, scheduled times only (no actual values in this
feed). Check its terms before any commercial use. Swapping in a paid source only requires a new
`parse_*` function that yields the same event dict.

Every event keeps: source, scheduled time (UTC), first-seen time (our ingestion time), last
seen time and a revision counter (changes to time/impact/forecast are counted). The decision
functions fail CLOSED: an unavailable or stale calendar blocks new signals.

Calendar text is untrusted input. It is only parsed into typed fields (time, currency, impact,
title string); nothing in it can change configuration, risk limits or permissions.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY"}
IMPACTS = {"High", "Medium", "Low", "Holiday", "Non-Economic"}

# Event-type tags from the title, used for reports and for longer blackouts on the biggest ones.
TAGS = [
    ("rate_decision", r"rate decision|cash rate|bank rate|policy rate|interest rate|monetary policy statement|FOMC Statement"),
    ("central_bank_speech", r"speaks|press conference|testifies|minutes"),
    ("inflation", r"\bCPI\b|inflation|\bPCE\b|\bPPI\b|HICP"),
    ("employment", r"non-farm|employment|unemployment|jobless|payroll|claimant|ADP"),
    ("gdp", r"\bGDP\b"),
    ("election", r"election|referendum|vote"),
    ("holiday", r"holiday|bank holiday"),
]
MAJOR = {"rate_decision", "inflation", "employment"}


@dataclass(frozen=True)
class CalEvent:
    id: str
    source: str
    title: str
    currency: str
    impact: str
    scheduled_at: str  # ISO UTC
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None

    @property
    def tag(self) -> str:
        for name, pat in TAGS:
            if re.search(pat, self.title, re.I):
                return name
        return "other"


def _clean(x, n=120) -> str | None:
    if x is None:
        return None
    s = re.sub(r"[\x00-\x1f<>]", "", str(x)).strip()
    return s[:n] or None


def parse_ff_json(items: list[dict]) -> list[CalEvent]:
    """Parse the Forex Factory weekly export. Unknown/garbled rows are skipped, not guessed."""
    out = []
    for it in items if isinstance(items, list) else []:
        try:
            cur = str(it.get("country", "")).upper().strip()
            imp = str(it.get("impact", "")).strip()
            if cur not in CURRENCIES or imp not in IMPACTS:
                continue
            ts = pd.Timestamp(it["date"])
            if ts.tzinfo is None:
                continue  # refuse to guess a time zone
            title = _clean(it.get("title"), 160) or "?"
            iso = ts.tz_convert("UTC").isoformat()
            eid = hashlib.sha1(f"ff|{cur}|{title}|{ts.date()}".encode()).hexdigest()[:16]
            out.append(CalEvent(eid, "forexfactory-json", title, cur, imp, iso,
                                _clean(it.get("forecast"), 30), _clean(it.get("previous"), 30), _clean(it.get("actual"), 30)))
        except Exception:
            continue
    return out


@dataclass
class Blackout:
    blocked: bool
    reasons: list[str]
    upcoming: list[CalEvent]


def blackout(symbol_ccys: tuple[str, str], now: datetime, events: list[CalEvent], last_fetch: datetime | None,
             before_min: float = 30, after_min: float = 30, major_extra_min: float = 30,
             impacts=("High",), max_age_h: float = 26, horizon_h: float = 24, fail_closed: bool = True) -> Blackout:
    now = pd.Timestamp(now)
    reasons: list[str] = []
    if last_fetch is None or (now - pd.Timestamp(last_fetch)) > pd.Timedelta(hours=max_age_h):
        if fail_closed:
            reasons.append("economic calendar unavailable or stale: new signals blocked (fail-closed)")
    rel = [e for e in events if e.currency in symbol_ccys and e.impact in impacts]
    upcoming = []
    for e in rel:
        t = pd.Timestamp(e.scheduled_at)
        extra = major_extra_min if e.tag in MAJOR else 0
        if t - pd.Timedelta(minutes=before_min + extra) <= now <= t + pd.Timedelta(minutes=after_min + extra):
            reasons.append(f"{e.currency} {e.title} at {t.strftime('%H:%M')} UTC ({e.impact})")
        if now <= t <= now + pd.Timedelta(hours=horizon_h):
            upcoming.append(e)
    return Blackout(bool(reasons), reasons, sorted(upcoming, key=lambda e: e.scheduled_at))


def events_during(symbol_ccys: tuple[str, str], start: datetime, end: datetime, events: list[CalEvent],
                  impacts=("High",)) -> list[CalEvent]:
    """High-impact events that fall inside a planned holding period (for signal context)."""
    a, b = pd.Timestamp(start), pd.Timestamp(end)
    return [e for e in events if e.currency in symbol_ccys and e.impact in impacts
            and a <= pd.Timestamp(e.scheduled_at) <= b]


async def fetch_ff(client, url: str = FF_URL) -> list[CalEvent]:
    r = await client.get(url, timeout=20)
    r.raise_for_status()
    return parse_ff_json(r.json())


def rows_to_events(rows: list[dict]) -> list[CalEvent]:
    return [CalEvent(r["id"], r["source"], r["title"], r["currency"], r["impact"], r["scheduled_at"], r.get("forecast"),
                     r.get("previous"), r.get("actual")) for r in rows]


def window(now: datetime, back_h: float = 6, fwd_h: float = 72) -> tuple[str, str]:
    n = pd.Timestamp(now)
    return (n - timedelta(hours=back_h)).isoformat(), (n + timedelta(hours=fwd_h)).isoformat()
