"""API-Football (api-sports.io) v3. Kamper, historikk, odds fra flere bookmakere,
fravær, oppstillinger og livedata.

Merk: Integrasjonen er skrevet etter leverandørens dokumenterte v3-format, men er
IKKE kjørt mot det ekte API-et fra utviklingsmiljøet (nettverket var blokkert).
Første produksjonsoppstart bør derfor kjøres med `python -m kampanalyse selftest`.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timezone

import httpx

from ..db import DB
from ..markets import Selection
from .base import Absence, Fixture, HistMatch, LiveEvent, LiveSnapshot, Lineup, OddsQuote, ProviderError

log = logging.getLogger(__name__)
BASE = "https://v3.football.api-sports.io"

_OU_RE = re.compile(r"^(Over|Under)\s+([0-9.]+)$")
_AH_RE = re.compile(r"^(Home|Away)\s*([+-]?[0-9.]+)$")


def parse_bet(bet_name: str, value: str) -> Selection | None:
    """Oversett API-Footballs bet-navn/verdi til internt Selection. Ukjente -> None."""
    v = value.strip()
    n = bet_name.strip()
    if n == "Match Winner":
        return {"Home": Selection("1X2", "H"), "Draw": Selection("1X2", "D"), "Away": Selection("1X2", "A")}.get(v)
    if n == "First Half Winner":
        return {"Home": Selection("1H_1X2", "H"), "Draw": Selection("1H_1X2", "D"), "Away": Selection("1H_1X2", "A")}.get(v)
    if n == "Double Chance":
        return {"Home/Draw": Selection("DC", "1X"), "Home/Away": Selection("DC", "12"),
                "Draw/Away": Selection("DC", "X2")}.get(v)
    if n == "Home/Away":  # Draw no bet
        return {"Home": Selection("DNB", "H"), "Away": Selection("DNB", "A")}.get(v)
    if n == "Both Teams Score":
        return {"Yes": Selection("BTTS", "Y"), "No": Selection("BTTS", "N")}.get(v)
    if n == "Asian Handicap":
        m = _AH_RE.match(v)
        if m:
            return Selection("AH", "H" if m.group(1) == "Home" else "A", float(m.group(2)))
        return None
    ou_markets = {"Goals Over/Under": "OU", "Goals Over/Under First Half": "1H_OU",
                  "Total - Home": "TT_H", "Total - Away": "TT_A",
                  "Cards Over/Under": "CARDS_OU", "Corners Over Under": "CORNERS_OU"}
    if n in ou_markets:
        m = _OU_RE.match(v)
        if m:
            return Selection(ou_markets[n], "O" if m.group(1) == "Over" else "U", float(m.group(2)))
    return None


class APIFootball:
    name = "API-Football"
    delay_note = "Livedata fra API-Football; boten henter med fast intervall, så varsler kan komme 1–2 min etter hendelsen."

    def __init__(self, key: str, db: DB, daily_cap: int = 7000, client: httpx.AsyncClient | None = None):
        self.key = key
        self.db = db
        self.daily_cap = daily_cap
        self.client = client or httpx.AsyncClient(timeout=20.0)

    # --- HTTP med kvote og gjentak ---
    def _count(self) -> int:
        k = f"apif_calls:{datetime.now(timezone.utc).date().isoformat()}"
        with self.db.tx():
            n = int(self.db.kv_get(k) or 0) + 1
            self.db.kv_set(k, str(n))
        return n

    async def _get(self, path: str, params: dict) -> list:
        if self._count() > self.daily_cap:
            raise ProviderError("Daglig forespørselskvote for API-Football er brukt opp")
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = await self.client.get(BASE + path, params=params, headers={"x-apisports-key": self.key})
                if r.status_code == 429 or r.status_code >= 500:
                    raise ProviderError(f"HTTP {r.status_code}")
                if r.status_code != 200:
                    raise ProviderError(f"HTTP {r.status_code}: {r.text[:200]}")
                body = r.json()
                errs = body.get("errors")
                if errs:
                    raise ProviderError(f"API-feil: {errs}")
                return body.get("response", [])
            except (httpx.HTTPError, ProviderError, ValueError) as e:
                last = e
                log.warning("API-Football %s feilet (forsøk %d): %s", path, attempt + 1, e)
                await asyncio.sleep(1.5 * (2 ** attempt))
        raise ProviderError(f"{path}: {last}")

    # --- data ---
    @staticmethod
    def _fixture(item: dict) -> Fixture:
        f, lg, t = item["fixture"], item["league"], item["teams"]
        return Fixture(
            id=str(f["id"]), league_id=int(lg["id"]), league_name=lg.get("name", ""), season=int(lg["season"]),
            kickoff=datetime.fromtimestamp(int(f["timestamp"]), tz=timezone.utc),
            home=t["home"]["name"], away=t["away"]["name"], status=f["status"]["short"],
            referee=f.get("referee"), venue=(f.get("venue") or {}).get("name"),
            coverage={"lineups": True, "injuries": True, "odds": True},
        )

    async def fixtures_on(self, d: date) -> list[Fixture]:
        items = await self._get("/fixtures", {"date": d.isoformat(), "timezone": "Europe/Oslo"})
        return [self._fixture(i) for i in items]

    async def history(self, league_id: int, season: int) -> list[HistMatch]:
        out: list[HistMatch] = []
        for s in (season - 1, season):
            try:
                items = await self._get("/fixtures", {"league": league_id, "season": s, "status": "FT-AET-PEN"})
            except ProviderError as e:
                log.warning("Historikk %s/%s mangler: %s", league_id, s, e)
                continue
            for i in items:
                sc = i.get("score", {})
                ft, ht = sc.get("fulltime") or {}, sc.get("halftime") or {}
                if ft.get("home") is None:
                    continue
                out.append(HistMatch(
                    date=datetime.fromtimestamp(int(i["fixture"]["timestamp"]), tz=timezone.utc).date(),
                    league_id=league_id, home=i["teams"]["home"]["name"], away=i["teams"]["away"]["name"],
                    hg=int(ft["home"]), ag=int(ft["away"]), ht_h=ht.get("home"), ht_a=ht.get("away")))
        return out

    async def odds(self, fixture: Fixture) -> list[OddsQuote]:
        items = await self._get("/odds", {"fixture": fixture.id})
        out: list[OddsQuote] = []
        for it in items:
            upd = it.get("update")
            checked = datetime.fromisoformat(upd.replace("Z", "+00:00")) if upd else datetime.now(timezone.utc)
            for bm in it.get("bookmakers", []):
                for bet in bm.get("bets", []):
                    for v in bet.get("values", []):
                        sel = parse_bet(bet.get("name", ""), str(v.get("value", "")))
                        try:
                            o = float(v.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        if sel and o > 1.0:
                            out.append(OddsQuote(fixture.id, bm.get("name", "?"), sel, o, checked, "apifootball",
                                                 is_nt=False))
        return out

    async def absences(self, fixture: Fixture) -> list[Absence] | None:
        try:
            items = await self._get("/injuries", {"fixture": fixture.id})
        except ProviderError:
            return None
        out = []
        for i in items:
            p = i.get("player", {})
            kind = "Ute" if p.get("type") == "Missing Fixture" else "Usikker"
            out.append(Absence(team=i.get("team", {}).get("name", "?"), player=p.get("name", "?"), kind=kind,
                               reason=p.get("reason") or "", source="API-Football /injuries"))
        return out

    async def lineups(self, fixture: Fixture) -> list[Lineup]:
        items = await self._get("/fixtures/lineups", {"fixture": fixture.id})
        return [Lineup(team=i["team"]["name"], formation=i.get("formation"),
                       start_xi=[x["player"]["name"] for x in i.get("startXI", [])], confirmed=True) for i in items]

    async def live(self, fixture_ids: list[str]) -> list[LiveSnapshot]:
        out: list[LiveSnapshot] = []
        now = datetime.now(timezone.utc)
        for chunk in [fixture_ids[i:i + 20] for i in range(0, len(fixture_ids), 20)]:
            items = await self._get("/fixtures", {"ids": "-".join(chunk)})
            for i in items:
                f, sc = i["fixture"], i.get("score", {})
                ft, ht = sc.get("fulltime") or {}, sc.get("halftime") or {}
                cards = corners = None
                stats = i.get("statistics") or []
                if stats:
                    def stat(name: str) -> int:
                        tot = 0
                        for team in stats:
                            for s in team.get("statistics", []):
                                if s.get("type") == name and s.get("value") is not None:
                                    tot += int(s["value"])
                        return tot
                    cards = stat("Yellow Cards") + stat("Red Cards")
                    corners = stat("Corner Kicks")
                events = [LiveEvent(minute=(e.get("time") or {}).get("elapsed"), type=e.get("type", ""),
                                    detail=e.get("detail", ""), team=(e.get("team") or {}).get("name", ""),
                                    player=(e.get("player") or {}).get("name")) for e in i.get("events") or []]
                out.append(LiveSnapshot(
                    fixture_id=str(f["id"]), status=f["status"]["short"], elapsed=f["status"].get("elapsed"),
                    home_goals=(i.get("goals") or {}).get("home"), away_goals=(i.get("goals") or {}).get("away"),
                    ft_home=ft.get("home"), ft_away=ft.get("away"), ht_home=ht.get("home"), ht_away=ht.get("away"),
                    cards=cards, corners=corners, events=events, fetched_at=now, provider_delay_note=self.delay_note))
        return out
