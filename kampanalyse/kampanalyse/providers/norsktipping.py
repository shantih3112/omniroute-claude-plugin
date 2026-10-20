"""Kilder for Norsk Tipping-odds (Oddsen).

Norsk Tipping har ingen offentlig odds-API. Boten omgår ikke innlogging eller
tilgangsbegrensninger og skraper ikke nettsiden. Tre nivåer brukes:

1. ManualNT: eier/administrator kontrollerer prisen i Oddsen og legger den inn
   med /ntodds. Dette er det eneste nivået som gir status «kontrollert».
2. OddsApiIoNT (valgfri, eksperimentell): tredjepartsleverandøren odds-api.io
   oppgir å levere Norsk Tipping-priser. Merkes «NT-odds via tredjepart – kontroller
   i Oddsen før innlevering». Ikke testet mot ekte API.
3. Ingen NT-kilde: forslaget merkes «Ikke verifisert hos Norsk Tipping» og
   referanseodds fra andre bookmakere vises med bookmakerens navn.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from ..db import DB
from ..markets import Selection
from ..timeutil import from_iso
from .base import Fixture, OddsQuote, ProviderError

log = logging.getLogger(__name__)
NT_ODDSEN_URL = "https://www.norsk-tipping.no/sport/oddsen"


class ManualNT:
    name = "Manuelt kontrollert i Oddsen"

    def __init__(self, db: DB):
        self.db = db

    async def nt_odds(self, fixture: Fixture) -> list[OddsQuote]:
        rows = self.db.all(
            """SELECT selection_key, odds, entered_at FROM nt_odds_manual m
               WHERE fixture_id=? AND entered_at=(SELECT MAX(entered_at) FROM nt_odds_manual
                    WHERE fixture_id=m.fixture_id AND selection_key=m.selection_key)""", (fixture.id,))
        return [OddsQuote(fixture.id, "Norsk Tipping", Selection.from_key(r["selection_key"]), r["odds"],
                          from_iso(r["entered_at"]), "manuell", is_nt=True, nt_verified=True, url=NT_ODDSEN_URL)
                for r in rows]


class OddsApiIoNT:
    """Eksperimentell adapter. Feltnavn er defensivt tolket; verifiser med selftest."""
    name = "odds-api.io (tredjepart)"
    BASE = "https://api.odds-api.io/v3"

    def __init__(self, key: str, bookmaker: str = "Norsk Tipping", client: httpx.AsyncClient | None = None):
        self.key = key
        self.bookmaker = bookmaker
        self.client = client or httpx.AsyncClient(timeout=20.0)
        self._events: dict[str, list[dict]] = {}

    async def _get(self, path: str, params: dict):
        params = {**params, "apiKey": self.key}
        r = await self.client.get(self.BASE + path, params=params)
        if r.status_code != 200:
            raise ProviderError(f"odds-api.io HTTP {r.status_code}")
        return r.json()

    async def _find_event(self, fixture: Fixture) -> str | None:
        day = fixture.kickoff.date().isoformat()
        if day not in self._events:
            data = await self._get("/events", {"sport": "football", "from": f"{day}T00:00:00Z",
                                                "to": f"{day}T23:59:59Z", "bookmaker": self.bookmaker})
            self._events[day] = data if isinstance(data, list) else data.get("data", [])
        norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
        for ev in self._events[day]:
            h, a = norm(str(ev.get("home", ""))), norm(str(ev.get("away", "")))
            if h and a and (h in norm(fixture.home) or norm(fixture.home) in h) and \
                    (a in norm(fixture.away) or norm(fixture.away) in a):
                return str(ev.get("id"))
        return None

    async def nt_odds(self, fixture: Fixture) -> list[OddsQuote]:
        try:
            ev = await self._find_event(fixture)
            if not ev:
                return []
            data = await self._get("/odds", {"eventId": ev, "bookmakers": self.bookmaker})
        except (httpx.HTTPError, ProviderError, ValueError) as e:
            log.warning("odds-api.io: %s", e)
            return []
        now = datetime.now(timezone.utc)
        out: list[OddsQuote] = []
        books = (data or {}).get("bookmakers", {}) if isinstance(data, dict) else {}
        markets = books.get(self.bookmaker, []) if isinstance(books, dict) else []
        for mk in markets:
            name = str(mk.get("name", "")).lower()
            for o in mk.get("odds", []):
                pairs: list[tuple[Selection, object]] = []
                if name in ("ml", "1x2", "match winner"):
                    pairs = [(Selection("1X2", "H"), o.get("home")), (Selection("1X2", "D"), o.get("draw")),
                             (Selection("1X2", "A"), o.get("away"))]
                elif name in ("totals", "over/under") and o.get("hdp") is not None:
                    line = float(o["hdp"])
                    pairs = [(Selection("OU", "O", line), o.get("over")), (Selection("OU", "U", line), o.get("under"))]
                elif name in ("both teams to score", "btts"):
                    pairs = [(Selection("BTTS", "Y"), o.get("yes")), (Selection("BTTS", "N"), o.get("no"))]
                for sel, val in pairs:
                    try:
                        f = float(val)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        continue
                    if f > 1.0:
                        out.append(OddsQuote(fixture.id, "Norsk Tipping", sel, f, now, "oddsapiio", is_nt=True,
                                             nt_verified=False, url=NT_ODDSEN_URL, event_ref=ev))
        return out
