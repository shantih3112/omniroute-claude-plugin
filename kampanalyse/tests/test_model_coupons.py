import math
from datetime import date, datetime, timedelta, timezone

from kampanalyse.analysis import Candidate, market_probabilities
from kampanalyse.coupons import BANDS, BAND_BY_CODE, build_all, build_coupon, overlap_report
from kampanalyse.markets import Result, Selection
from kampanalyse.model import fit, price_equivalent, result_distribution
from kampanalyse.providers.base import Fixture, HistMatch, OddsQuote


def _hist():
    out, d = [], date(2026, 1, 1)
    teams = ["A", "B", "C", "D"]
    for i in range(60):
        h, a = teams[i % 4], teams[(i + 1) % 4]
        out.append(HistMatch(d + timedelta(days=i * 3), 1, h, a, 3 if h == "A" else 1, 0 if h == "A" else 1))
    return out


def test_fit_uses_only_past_matches():
    hist = _hist()
    ref = hist[30].date
    r = fit(hist, ref)
    assert r.matches_used == sum(1 for m in hist if m.date < ref)
    # Endring av fremtidige kamper skal ikke påvirke estimatet (ingen lekkasje)
    changed = hist[:30] + [HistMatch(m.date, 1, m.home, m.away, 9, 9) for m in hist[30:]]
    r2 = fit(changed, ref)
    assert r.attack == r2.attack and r.defence == r2.defence
    assert r.attack["A"] > r.attack["B"]


def test_distribution_sums_and_dnb_price_equivalent():
    dist = result_distribution(Selection("DNB", "H"), 1.6, 1.0)
    assert abs(sum(dist.values()) - 1) < 1e-9
    q, push = price_equivalent(dist)
    pw, pd = dist[Result.WON], dist[Result.VOID]
    assert abs(1 / q - (1 - pd) / pw) < 1e-9
    assert abs(push - pd) < 1e-9
    q1x2, _ = price_equivalent(result_distribution(Selection("1X2", "H"), 1.6, 1.0))
    assert q > q1x2


def _quotes(fid, books):
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    out = []
    for b, (h, d, a) in books.items():
        for o, v in zip("HDA", (h, d, a)):
            out.append(OddsQuote(fid, b, Selection("1X2", o), v, now, "test"))
    return out


def test_market_consensus_and_double_chance():
    mk = market_probabilities(_quotes("1", {"x": (2.0, 3.4, 4.0), "y": (2.05, 3.3, 3.9)}))
    assert abs(sum(mk[Selection("1X2", o)][0] for o in "HDA") - 1) < 1e-9
    assert mk[Selection("1X2", "H")][1] == 2
    assert abs(mk[Selection("DC", "1X")][0] - (mk[Selection("1X2", "H")][0] + mk[Selection("1X2", "D")][0])) < 1e-12


def _cand(i, odds, q, tags=("høy_treff",), fixture=None, quality=0.9):
    fx = fixture or Fixture(f"f{i}", 1, "L", 2026, datetime(2026, 10, 20, 12 + i % 8, tzinfo=timezone.utc), f"H{i}", f"A{i}")
    return Candidate(fx, Selection("1X2", "H"), f"H{i} vinner", odds, "test", "REFERANSE", fx.kickoff, odds, q, q, q, 0.0,
                     0.02, q * odds - 1, (q - 0.02) * odds - 1, 1.3, quality, list(tags))


def test_coupon_one_leg_per_fixture_and_in_band():
    pool = [_cand(i, 1.5 + 0.1 * (i % 5), 0.66) for i in range(12)]
    shared = pool[0].fixture
    pool.append(_cand(99, 1.6, 0.64, fixture=shared))
    drafts, empty = build_all(pool)
    assert drafts
    for d in drafts:
        fx = [c.fixture.id for c in d.legs]
        assert len(fx) == len(set(fx))
        assert d.band.lo <= d.total_odds <= d.band.hi
        assert abs(d.total_odds - round(math.prod(c.odds for c in d.legs), 2)) < 1e-9
        assert not d.verified_nt  # referanseodds er aldri NT-verifisert


def test_no_filler_legs_when_pool_is_weak():
    """Svake ledd (utenfor kvalitetskrav) skal ikke brukes for å nå totalodds."""
    weak = [_cand(i, 3.0, 0.3, tags=(), quality=0.4) for i in range(10)]
    assert build_coupon(weak, BAND_BY_CODE["B"], __import__("collections").Counter()) is None
    drafts, empty = build_all(weak)
    assert drafts == [] and set(empty) == {b.code for b in BANDS}


def test_blocked_legs_are_not_reused_and_overlap_reported():
    pool = [_cand(i, 1.7, 0.62) for i in range(6)]
    blocked = {(c.fixture.id, c.selection) for c in pool[:5]}
    drafts, _ = build_all(pool, [BAND_BY_CODE["B"]], blocked)
    assert drafts == []
    drafts, _ = build_all(pool, [BAND_BY_CODE["B"], BAND_BY_CODE["C"]])
    rep = overlap_report(drafts)
    assert isinstance(rep, list)
