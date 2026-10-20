"""Felles datatyper og grensesnitt for datakilder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from ..markets import Selection

LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"}
FINAL_STATUSES = {"FT", "AET", "PEN"}
VOID_STATUSES = {"PST", "CANC", "ABD", "AWD", "WO"}
NOT_STARTED = {"NS", "TBD"}


class ProviderError(Exception):
    """Feil fra datakilde (nett, kvote, ugyldig svar)."""


@dataclass
class Fixture:
    id: str
    league_id: int
    league_name: str
    season: int
    kickoff: datetime
    home: str
    away: str
    status: str = "NS"
    referee: str | None = None
    venue: str | None = None
    coverage: dict = field(default_factory=dict)  # f.eks. {"lineups": True, "injuries": True, "odds": True}


@dataclass
class OddsQuote:
    fixture_id: str
    bookmaker: str
    selection: Selection
    odds: float
    checked_at: datetime
    source: str            # "apifootball", "oddsapiio", "manuell", "demo"
    is_nt: bool = False    # True KUN når prisen er Norsk Tippings egen pris
    nt_verified: bool = False  # True når bruker/admin har kontrollert prisen i NT-kupongen
    url: str | None = None
    event_ref: str | None = None


@dataclass
class HistMatch:
    date: date
    league_id: int
    home: str
    away: str
    hg: int
    ag: int
    hxg: float | None = None
    axg: float | None = None
    ht_h: int | None = None
    ht_a: int | None = None


@dataclass
class Absence:
    team: str
    player: str
    kind: str      # "Ute" / "Usikker"
    reason: str
    source: str


@dataclass
class Lineup:
    team: str
    formation: str | None
    start_xi: list[str]
    confirmed: bool


@dataclass
class LiveEvent:
    minute: int | None
    type: str          # Goal, Card, Var, subst
    detail: str
    team: str
    player: str | None

    def key(self) -> str:
        return f"{self.minute}|{self.type}|{self.detail}|{self.team}|{self.player}"


@dataclass
class LiveSnapshot:
    fixture_id: str
    status: str
    elapsed: int | None
    home_goals: int | None          # Inkl. ev. ekstraomganger
    away_goals: int | None
    ft_home: int | None             # Ordinær tid (brukes til oppgjør)
    ft_away: int | None
    ht_home: int | None
    ht_away: int | None
    cards: int | None
    corners: int | None
    events: list[LiveEvent]
    fetched_at: datetime
    provider_delay_note: str = ""


class DataProvider(Protocol):
    name: str
    delay_note: str

    async def fixtures_on(self, d: date) -> list[Fixture]: ...
    async def history(self, league_id: int, season: int) -> list[HistMatch]: ...
    async def odds(self, fixture: Fixture) -> list[OddsQuote]: ...
    async def absences(self, fixture: Fixture) -> list[Absence] | None: ...
    async def lineups(self, fixture: Fixture) -> list[Lineup]: ...
    async def live(self, fixture_ids: list[str]) -> list[LiveSnapshot]: ...


class NTOddsSource(Protocol):
    name: str

    async def nt_odds(self, fixture: Fixture) -> list[OddsQuote]: ...
