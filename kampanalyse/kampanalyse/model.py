"""Mål-modell: tidsvektet Poisson (Maher) med Dixon-Coles-korreksjon for lave resultater.

- Lagstyrke (angrep/forsvar) estimeres fra kamper FØR analysetidspunktet, med
  eksponentiell tidsvekting (halveringstid) og krymping mot ligasnitt.
- Når xG finnes i historikken blandes mål og xG 50/50 (mer stabilt enn mål alene).
- Modellen er IKKE validert mot ekte data i denne leveransen. Estimatene blandes
  derfor bare svakt inn i markedets marginfrie sannsynlighet (se config.model_weight).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from .markets import Result, Selection, MatchStats, settle
from .providers.base import HistMatch

MAX_GOALS = 10


@dataclass
class Ratings:
    attack: dict[str, float]
    defence: dict[str, float]     # >1 = slipper inn mer enn snittet
    home_adv: float
    n_eff: dict[str, float]       # effektivt antall kamper (vektet)
    league_avg: float
    ref_date: date
    matches_used: int
    rho: float = -0.05
    xg_share: float = 0.0
    recent: dict[str, list[HistMatch]] = field(default_factory=dict)

    def expected_goals(self, home: str, away: str) -> tuple[float, float] | None:
        if home not in self.attack or away not in self.attack:
            return None
        lh = self.attack[home] * self.defence[away] * self.home_adv
        la = self.attack[away] * self.defence[home]
        return lh, la


def fit(matches: list[HistMatch], ref_date: date, half_life_days: float = 180.0,
        prior_matches: float = 4.0, iterations: int = 60) -> Ratings:
    """Estimer lagstyrker kun fra kamper strengt før ref_date (ingen lekkasje)."""
    past = [m for m in matches if m.date < ref_date]
    teams = sorted({m.home for m in past} | {m.away for m in past})
    if not past:
        return Ratings({}, {}, 1.0, {}, 1.3, ref_date, 0)
    lam = math.log(2) / half_life_days
    rows = []
    xg_rows = 0
    for m in past:
        w = math.exp(-lam * (ref_date - m.date).days)
        hg, ag = float(m.hg), float(m.ag)
        if m.hxg is not None and m.axg is not None:
            hg, ag = 0.5 * hg + 0.5 * m.hxg, 0.5 * ag + 0.5 * m.axg
            xg_rows += 1
        rows.append((m.home, m.away, hg, ag, w))

    tw = sum(r[4] for r in rows)
    avg_h = sum(r[2] * r[4] for r in rows) / tw
    avg_a = sum(r[3] * r[4] for r in rows) / tw
    league_avg = (avg_h + avg_a) / 2
    att = {t: league_avg for t in teams}
    dfn = {t: 1.0 for t in teams}
    home = max(0.8, min(1.6, avg_h / max(avg_a, 0.1)))
    n_eff: dict[str, float] = defaultdict(float)
    for h, a, _, _, w in rows:
        n_eff[h] += w
        n_eff[a] += w

    for _ in range(iterations):
        num: dict[str, float] = defaultdict(float)
        den: dict[str, float] = defaultdict(float)
        for h, a, hg, ag, w in rows:
            num[h] += w * hg
            den[h] += w * dfn[a] * home
            num[a] += w * ag
            den[a] += w * dfn[h]
        att = {t: (num[t] + prior_matches * league_avg) / (den[t] + prior_matches) for t in teams}
        num = defaultdict(float)
        den = defaultdict(float)
        for h, a, hg, ag, w in rows:
            num[a] += w * hg
            den[a] += w * att[h] * home
            num[h] += w * ag
            den[h] += w * att[a]
        dfn = {t: (num[t] + prior_matches) / (den[t] + prior_matches) for t in teams}
        mean_d = sum(dfn.values()) / len(dfn)
        dfn = {t: v / mean_d for t, v in dfn.items()}
        hn = sum(w * hg for _, _, hg, _, w in rows)
        hd = sum(w * att[h] * dfn[a] for h, a, _, _, w in rows)
        home = max(0.8, min(1.6, hn / hd)) if hd > 0 else home

    recent: dict[str, list[HistMatch]] = defaultdict(list)
    for m in sorted(past, key=lambda x: x.date, reverse=True):
        for t in (m.home, m.away):
            if len(recent[t]) < 10:
                recent[t].append(m)
    return Ratings(att, dfn, home, dict(n_eff), league_avg, ref_date, len(past),
                   xg_share=xg_rows / len(past), recent=dict(recent))


def _pois(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _tau(i: int, j: int, lh: float, la: float, rho: float) -> float:
    if i == 0 and j == 0:
        return 1 - lh * la * rho
    if i == 0 and j == 1:
        return 1 + lh * rho
    if i == 1 and j == 0:
        return 1 + la * rho
    if i == 1 and j == 1:
        return 1 - rho
    return 1.0


def score_matrix(lh: float, la: float, rho: float = -0.05) -> list[list[float]]:
    m = [[_pois(i, lh) * _pois(j, la) * _tau(i, j, lh, la, rho) for j in range(MAX_GOALS + 1)]
         for i in range(MAX_GOALS + 1)]
    s = sum(map(sum, m))
    return [[x / s for x in row] for row in m]


def result_distribution(sel: Selection, lh: float, la: float, rho: float = -0.05) -> dict[Result, float] | None:
    """Sannsynlighetsfordeling over oppgjørsutfall for valget (håndterer push/kvartlinjer).
    1. omgang modelleres med 45 % av forventede mål (vanlig empirisk andel; forenkling)."""
    if sel.market in ("CARDS_OU", "CORNERS_OU"):
        return None
    first_half = sel.market in ("1H_1X2", "1H_OU")
    fh = 0.45 if first_half else 1.0
    mat = score_matrix(lh * fh, la * fh, rho if not first_half else 0.0)
    dist: dict[Result, float] = defaultdict(float)
    for i, row in enumerate(mat):
        for j, p in enumerate(row):
            stats = MatchStats(i, j, ht_home=i, ht_away=j) if first_half else MatchStats(i, j)
            r = settle(sel, stats)
            if r is None:
                return None
            dist[r] += p
    return dict(dist)


def price_equivalent(dist: dict[Result, float]) -> tuple[float, float]:
    """(q, p_void): q = 1/rettferdig odds, der rettferdig odds gir forventet verdi 0.

    For valg uten push er q lik vinnersannsynligheten."""
    pw = dist.get(Result.WON, 0)
    phw, phl, pv = dist.get(Result.HALF_WON, 0), dist.get(Result.HALF_LOST, 0), dist.get(Result.VOID, 0)
    # EV(o) = pw*o + phw*(o+1)/2 + pv + phl*0.5 - 1 = 0  -> o = (1 - pv - phw/2 - phl/2) / (pw + phw/2)
    denom = pw + phw / 2
    if denom <= 0:
        return 0.0, pv
    fair = (1 - pv - phw / 2 - phl / 2) / denom
    return 1.0 / fair, pv + phw / 2 + phl / 2


def poisson_over(lam: float, line: float) -> float:
    """P(X > line) for Poisson, brukt til kort/hjørner når data finnes."""
    k = math.floor(line)
    return 1 - sum(_pois(i, lam) for i in range(k + 1))
