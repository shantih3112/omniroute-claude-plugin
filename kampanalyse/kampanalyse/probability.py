"""Sannsynlighetsregning: implisitt sannsynlighet, marginfjerning, forventet verdi."""
from __future__ import annotations

import math
from statistics import median


def implied(odds: float) -> float:
    """Rå implisitt sannsynlighet = 1 / desimalodds (inkluderer bookmakerens margin)."""
    if odds <= 1.0:
        raise ValueError("odds må være > 1")
    return 1.0 / odds


def overround(odds: list[float]) -> float:
    return sum(1.0 / o for o in odds) - 1.0


def devig_proportional(odds: list[float]) -> list[float]:
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def devig_power(odds: list[float], tol: float = 1e-10) -> list[float]:
    """Power-metoden: finn k slik at sum((1/o)^k) = 1. Håndterer favoritt/longshot-skjevhet
    bedre enn proporsjonal fjerning. Faller tilbake til proporsjonal ved problemer."""
    inv = [1.0 / o for o in odds]
    if sum(inv) <= 1.0:
        return devig_proportional(odds)
    lo, hi = 1.0, 10.0
    for _ in range(200):
        k = (lo + hi) / 2
        s = sum(x ** k for x in inv)
        if abs(s - 1.0) < tol:
            break
        if s > 1.0:
            lo = k
        else:
            hi = k
    out = [x ** k for x in inv]
    s = sum(out)
    return [x / s for x in out]


def consensus(probs_by_book: list[list[float]]) -> list[float] | None:
    """Median av marginfrie sannsynligheter på tvers av bookmakere, normalisert."""
    if not probs_by_book:
        return None
    n = len(probs_by_book[0])
    med = [median(p[i] for p in probs_by_book) for i in range(n)]
    s = sum(med)
    return [x / s for x in med]


def expected_value(prob: float, odds: float) -> float:
    """Forventet verdi per innsatsenhet: p × odds − 1."""
    return prob * odds - 1.0


def min_acceptable_odds(prob_conservative: float, min_edge: float) -> float:
    """Laveste odds der det konservative estimatet fortsatt gir min_edge i forventet verdi."""
    if prob_conservative <= 0:
        return math.inf
    return (1.0 + min_edge) / prob_conservative


def blend(market_p: float, model_p: float | None, weight: float) -> float:
    """Krymp modellen mot markedet. weight=0 -> rent marked; weight=1 -> ren modell."""
    if model_p is None:
        return market_p
    return market_p + weight * (model_p - market_p)


def conservative(p: float, uncertainty: float) -> float:
    """Nedre anslag: trekk fra usikkerhet (sannsynlighetspoeng). Aldri under 0,1 %."""
    return max(0.001, p - uncertainty)
