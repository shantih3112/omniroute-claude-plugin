"""DEMO-leverandør med FIKTIVE lag, kamper og odds.

Alt herfra er eksempeldata for å vise og teste flyten uten API-nøkler.
Lagene, ligaen og prisene finnes ikke. Alle meldinger merkes «DEMO – EKSEMPELDATA».
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import date, time, timedelta

from ..markets import Selection
from ..model import result_distribution, price_equivalent, poisson_over
from ..probability import devig_proportional
from ..timeutil import Clock, local_at
from .base import Absence, Fixture, HistMatch, LiveEvent, LiveSnapshot, Lineup, OddsQuote

TEAMS = [
    "Nordby FK", "Fjellstad IL", "Havnevik SK", "Elvedal BK", "Skoglia FK", "Brattøy IL",
    "Vestmark SK", "Østgård FK", "Kystby IF", "Dalheim BK", "Sjøvik FK", "Granlund IL",
    "Myrvoll SK", "Lysefjord FK", "Tindvik IF", "Solbakken BK",
]
LEAGUE_ID = 9001
LEAGUE = "Demoligaen (fiktiv)"
REF_BOOKS = ["Referanse A (fiktiv)", "Referanse B (fiktiv)", "Referanse C (fiktiv)", "Referanse D (fiktiv)"]
KICKOFFS = [time(13, 0), time(15, 0), time(15, 0), time(17, 0), time(18, 0), time(19, 0), time(20, 0), time(20, 45)]


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


class DemoProvider:
    name = "DEMO (fiktive data)"
    delay_note = "DEMO: simulerte livedata."

    def __init__(self, clock: Clock, seed: int = 7):
        self.clock = clock
        rnd = random.Random(seed)
        self.att = {t: math.exp(rnd.gauss(0, 0.22)) * 1.35 for t in TEAMS}
        self.dfn = {t: math.exp(rnd.gauss(0, 0.2)) for t in TEAMS}
        self.home_adv = 1.22
        self.fixtures: dict[str, Fixture] = {}
        self.fail_live = False       # For tester av driftsavvik
        self.corrections: dict[str, tuple[int, int]] = {}  # fixture_id -> korrigert sluttresultat

    def lam(self, h: str, a: str) -> tuple[float, float]:
        return self.att[h] * self.dfn[a] * self.home_adv, self.att[a] * self.dfn[h]

    async def fixtures_on(self, d: date) -> list[Fixture]:
        rnd = random.Random(_seed("fx", d))
        teams = TEAMS[:]
        rnd.shuffle(teams)
        out = []
        for i in range(8):
            h, a = teams[2 * i], teams[2 * i + 1]
            fid = f"demo-{d.isoformat()}-{i + 1}"
            fx = Fixture(fid, LEAGUE_ID, LEAGUE, d.year, local_at(d, KICKOFFS[i]), h, a, "NS",
                         referee=f"Dommer {chr(65 + i)} (fiktiv)", venue=f"{h.split()[0]} stadion",
                         coverage={"lineups": True, "injuries": True, "odds": True})
            self.fixtures[fid] = fx
            out.append(fx)
        return out

    async def history(self, league_id: int, season: int) -> list[HistMatch]:
        rnd = random.Random(_seed("hist", season))
        start = date(season, 3, 1) - timedelta(days=365)
        today = self.clock.now().date()
        out = []
        d = start
        while d < today:
            teams = TEAMS[:]
            rnd.shuffle(teams)
            for i in range(8):
                h, a = teams[2 * i], teams[2 * i + 1]
                lh, la = self.lam(h, a)
                hg, ag = _poisson(rnd, lh), _poisson(rnd, la)
                out.append(HistMatch(d, LEAGUE_ID, h, a, hg, ag, hxg=round(lh * rnd.uniform(0.8, 1.2), 2),
                                     axg=round(la * rnd.uniform(0.8, 1.2), 2), ht_h=min(hg, _poisson(rnd, lh * .45)),
                                     ht_a=min(ag, _poisson(rnd, la * .45))))
            d += timedelta(days=7)
        return out

    def _true_q(self, fx: Fixture, sel: Selection) -> float | None:
        lh, la = self.lam(fx.home, fx.away)
        if sel.market == "CARDS_OU":
            p = poisson_over(4.3, sel.line)
            return p if sel.outcome == "O" else 1 - p
        dist = result_distribution(sel, lh, la)
        return price_equivalent(dist)[0] if dist else None

    def _markets(self) -> list[list[Selection]]:
        return [
            [Selection("1X2", "H"), Selection("1X2", "D"), Selection("1X2", "A")],
            [Selection("OU", "O", 2.5), Selection("OU", "U", 2.5)],
            [Selection("OU", "O", 1.5), Selection("OU", "U", 1.5)],
            [Selection("OU", "O", 3.5), Selection("OU", "U", 3.5)],
            [Selection("BTTS", "Y"), Selection("BTTS", "N")],
            [Selection("DNB", "H"), Selection("DNB", "A")],
            [Selection("AH", "H", -0.5), Selection("AH", "A", 0.5)],
            [Selection("AH", "H", -1.0), Selection("AH", "A", 1.0)],
            [Selection("AH", "H", 0.25), Selection("AH", "A", -0.25)],
            [Selection("TT_H", "O", 1.5), Selection("TT_H", "U", 1.5)],
            [Selection("TT_A", "O", 0.5), Selection("TT_A", "U", 0.5)],
            [Selection("DC", "1X"), Selection("DC", "X2"), Selection("DC", "12")],
            [Selection("CARDS_OU", "O", 4.5), Selection("CARDS_OU", "U", 4.5)],
        ]

    def _quotes(self, fx: Fixture, book: str, margin: float, noise: float, is_nt: bool) -> list[OddsQuote]:
        rnd = random.Random(_seed("odds", fx.id, book))
        now = self.clock.now()
        out = []
        for group in self._markets():
            qs = [self._true_q(fx, s) for s in group]
            if any(q is None for q in qs):
                continue
            noisy = [max(0.02, q * math.exp(rnd.gauss(0, noise))) for q in qs]
            if group[0].market == "DC":
                fair = noisy  # Dobbeltsjanse summerer til 2; enkel margin per utfall
                prices = [round(1 / (p * (1 + margin)), 2) for p in fair]
            else:
                norm = devig_proportional([1 / p for p in noisy])
                prices = [round(1 / (p * (1 + margin)), 2) for p in norm]
            for s, o in zip(group, prices):
                if o > 1.01:
                    out.append(OddsQuote(fx.id, book, s, o, now, "demo", is_nt=is_nt))
        return out

    async def odds(self, fixture: Fixture) -> list[OddsQuote]:
        out = []
        for i, b in enumerate(REF_BOOKS):
            out += self._quotes(fixture, b, margin=0.03 + 0.01 * i, noise=0.035, is_nt=False)
        return out

    async def nt_odds(self, fixture: Fixture) -> list[OddsQuote]:
        return self._quotes(fixture, "Norsk Tipping (DEMO-pris, fiktiv)", margin=0.065, noise=0.06, is_nt=True)

    async def absences(self, fixture: Fixture) -> list[Absence] | None:
        rnd = random.Random(_seed("abs", fixture.id))
        out = []
        for team in (fixture.home, fixture.away):
            for k in range(rnd.randint(0, 2)):
                out.append(Absence(team, f"Spiller {rnd.randint(2, 30)} ({team.split()[0]})",
                                   rnd.choice(["Ute", "Usikker"]), rnd.choice(["Kneskade", "Karantene", "Sykdom"]),
                                   "DEMO"))
        return out

    async def lineups(self, fixture: Fixture) -> list[Lineup]:
        if self.clock.now() < fixture.kickoff - timedelta(minutes=60):
            return []
        return [Lineup(t, "4-3-3", [f"{t.split()[0]} spiller {n}" for n in range(1, 12)], True)
                for t in (fixture.home, fixture.away)]

    async def live(self, fixture_ids: list[str]) -> list[LiveSnapshot]:
        if self.fail_live:
            from .base import ProviderError
            raise ProviderError("DEMO: simulert feil i livedata")
        now = self.clock.now()
        out = []
        for fid in fixture_ids:
            if fid not in self.fixtures and fid.startswith("demo-"):
                # Tilstandsløs som en ekte leverandør: gjenskap kampen etter omstart
                await self.fixtures_on(date.fromisoformat(fid[5:15]))
            fx = self.fixtures.get(fid)
            if not fx:
                continue
            minutes = (now - fx.kickoff).total_seconds() / 60
            if minutes < 0:
                out.append(LiveSnapshot(fid, "NS", None, None, None, None, None, None, None, None, None, [], now))
                continue
            rnd = random.Random(_seed("live", fid))
            lh, la = self.lam(fx.home, fx.away)
            goals = [(rnd.randint(1, 94), fx.home) for _ in range(_poisson(rnd, lh))] + \
                    [(rnd.randint(1, 94), fx.away) for _ in range(_poisson(rnd, la))]
            cards = sorted(rnd.randint(5, 94) for _ in range(_poisson(rnd, 4.3)))
            # Spilletid: 45 + pause 15 + 45 + tillegg
            if minutes < 47:
                played, status = minutes, "1H"
            elif minutes < 62:
                played, status = 45, "HT"
            elif minutes < 112:
                played, status = minutes - 17, "2H"
            else:
                played, status = 95, "FT"
            events = [LiveEvent(m, "Goal", "Normal Goal", t, None) for m, t in sorted(goals) if m <= played]
            events += [LiveEvent(m, "Card", "Yellow Card", fx.home if m % 2 else fx.away, None) for m in cards if m <= played]
            hg = sum(1 for e in events if e.type == "Goal" and e.team == fx.home)
            ag = sum(1 for e in events if e.type == "Goal" and e.team == fx.away)
            ht = [e for e in events if e.type == "Goal" and e.minute <= 45]
            hth = sum(1 for e in ht if e.team == fx.home)
            hta = sum(1 for e in ht if e.team == fx.away)
            if status == "FT" and fid in self.corrections:
                hg, ag = self.corrections[fid]
            ncards = sum(1 for e in events if e.type == "Card")
            out.append(LiveSnapshot(fid, status, int(played), hg, ag, hg if status == "FT" else None,
                                    ag if status == "FT" else None, hth if played >= 45 else None,
                                    hta if played >= 45 else None, ncards, None, events, now, self.delay_note))
        return out


def _poisson(rnd: random.Random, lam: float) -> int:
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= l:
            return k
        k += 1
