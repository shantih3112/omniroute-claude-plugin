"""Bygging av kombinasjonsbonger fra allerede kvalifiserte enkeltspill.

Regler:
- Maks ett ledd per kamp (unngår korrelerte ledd og bet builder-priser som ikke kan
  beregnes ved å multiplisere enkeltodds).
- Kun ledd som er kvalifisert som enkeltspill. Ingen «fyll» for å nå totalodds.
- Treffanslag = produktet av ledd-anslag. Forutsetter uavhengighet MELLOM ulike kamper
  og arver modellens usikkerhet; vises derfor som grovt anslag.
- Gjenbruk av samme ledd i flere bonger straffes, og overlapp rapporteres.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .analysis import Candidate


@dataclass(frozen=True)
class Band:
    code: str
    title: str
    lo: float
    hi: float
    min_legs: int
    max_legs: int
    min_quality: float
    speculative: bool


BANDS = [
    Band("B", "Hovedbong", 3.0, 10.0, 2, 4, 0.65, False),
    Band("C", "Kombinasjon 10–20", 10.0, 20.0, 2, 5, 0.6, False),
    Band("D", "Kombinasjon 20–40", 20.0, 40.0, 3, 6, 0.55, True),
    Band("E", "Kombinasjon 40–70", 40.0, 70.0, 3, 7, 0.55, True),
    Band("F", "Kombinasjon 70–100", 70.0, 100.0, 4, 8, 0.55, True),
    Band("G", "Ekstrembong 100+", 100.0, 1000.0, 5, 10, 0.55, True),
]
BAND_BY_CODE = {b.code: b for b in BANDS}


@dataclass
class CouponDraft:
    band: Band
    legs: list[Candidate]
    total_odds: float
    hit_est: float
    ev_est: float
    verified_nt: bool
    notes: list[str] = field(default_factory=list)


def _evaluate(legs: list[Candidate]) -> tuple[float, float, float]:
    total = math.prod(c.odds for c in legs)
    hit = math.prod(c.hit for c in legs)
    # Forventet retur per enhet ≈ Π (1 + EV_i) for uavhengige ledd
    ev = math.prod(1 + c.ev_point for c in legs) - 1
    return total, hit, ev


def build_coupon(pool: list[Candidate], band: Band, used: Counter, max_leg_reuse: int = 2,
                 beam: int = 300) -> CouponDraft | None:
    legs_pool = [c for c in pool if c.quality >= band.min_quality and used[(c.fixture.id, c.selection)] < max_leg_reuse]
    # Hovedbongen bruker bare ledd med høy treffmulighet eller dokumentert verdi.
    if band.code == "B":
        legs_pool = [c for c in legs_pool if "høy_treff" in c.tags or "verdi" in c.tags]
    legs_pool.sort(key=lambda c: c.score, reverse=True)
    legs_pool = legs_pool[:40]
    if len(legs_pool) < band.min_legs:
        return None

    def objective(state: list[int]) -> float:
        legs = [legs_pool[i] for i in state]
        _, hit, ev = _evaluate(legs)
        reuse = sum(used[(c.fixture.id, c.selection)] for c in legs)
        return math.log(max(hit, 1e-9)) + 2.0 * ev - 0.35 * reuse

    states: list[list[int]] = [[]]
    best: tuple[float, list[int]] | None = None
    for _ in range(band.max_legs):
        nxt: list[list[int]] = []
        for st in states:
            fixtures = {legs_pool[i].fixture.id for i in st}
            total = math.prod(legs_pool[i].odds for i in st) if st else 1.0
            start = st[-1] + 1 if st else 0
            for i in range(start, len(legs_pool)):
                c = legs_pool[i]
                if c.fixture.id in fixtures or total * c.odds > band.hi:
                    continue
                nxt.append(st + [i])
        if not nxt:
            break
        # Rangér mellomtilstander med kreditt for fremdrift mot nedre grense, ellers
        # ville strålesøket bare beholde lavodds-kombinasjoner og aldri nå høye bånd.
        nxt.sort(key=lambda st: objective(st) + math.log(min(band.lo, math.prod(legs_pool[i].odds for i in st))),
                 reverse=True)
        states = nxt[:beam]
        for st in states:
            tot = math.prod(legs_pool[i].odds for i in st)
            if len(st) >= band.min_legs and band.lo <= tot <= band.hi:
                score = objective(st)
                if best is None or score > best[0]:
                    best = (score, st)
    if best is None:
        return None
    legs = sorted((legs_pool[i] for i in best[1]), key=lambda c: c.fixture.kickoff)
    total, hit, ev = _evaluate(legs)
    verified = all(c.odds_kind == "NT_KONTROLLERT" for c in legs)
    notes = []
    if any(c.odds_kind == "REFERANSE" for c in legs):
        notes.append("Minst ett ledd mangler Norsk Tipping-pris – ikke klar til innlevering.")
    if any(c.push > 0 for c in legs):
        notes.append("Inneholder ledd med mulig tilbakebetaling/halv gevinst – totalodds kan bli lavere.")
    return CouponDraft(band, legs, round(total, 2), hit, ev, verified, notes)


def build_all(pool: list[Candidate], bands: list[Band] | None = None,
              blocked: set | None = None) -> tuple[list[CouponDraft], list[str]]:
    """blocked: (fixture_id, Selection) som ikke skal brukes (f.eks. ledd i allerede aktive bonger)."""
    used: Counter = Counter({k: 99 for k in (blocked or set())})
    out: list[CouponDraft] = []
    empty: list[str] = []
    for band in bands or BANDS:
        d = build_coupon(pool, band, used)
        if d is None:
            empty.append(band.code)
            continue
        for c in d.legs:
            used[(c.fixture.id, c.selection)] += 1
        out.append(d)
    return out, empty


def overlap_report(drafts: list[CouponDraft]) -> list[tuple[str, list[str]]]:
    """Kamper som inngår i flere bonger: ett resultat kan ødelegge flere samtidig."""
    by_fx: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for d in drafts:
        for c in d.legs:
            by_fx.setdefault(c.fixture.id, []).append(d.band.code)
            names[c.fixture.id] = f"{c.fixture.home} – {c.fixture.away}"
    return [(names[f], codes) for f, codes in by_fx.items() if len(codes) > 1]
