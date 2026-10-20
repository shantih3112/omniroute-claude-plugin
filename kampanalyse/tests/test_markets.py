import pytest

from kampanalyse.markets import LiveState, MatchStats, Result, Selection, live_state, payout_factor, settle
from kampanalyse.probability import devig_power, devig_proportional, expected_value, implied


@pytest.mark.parametrize("sel,score,expected", [
    (Selection("1X2", "H"), (2, 1), Result.WON),
    (Selection("1X2", "D"), (1, 1), Result.WON),
    (Selection("1X2", "A"), (1, 1), Result.LOST),
    (Selection("DC", "1X"), (0, 0), Result.WON),
    (Selection("DC", "12"), (0, 0), Result.LOST),
    (Selection("DNB", "H"), (1, 1), Result.VOID),
    (Selection("DNB", "A"), (0, 1), Result.WON),
    (Selection("AH", "H", -0.5), (1, 0), Result.WON),
    (Selection("AH", "H", -1.0), (1, 0), Result.VOID),
    (Selection("AH", "H", -0.75), (1, 0), Result.HALF_WON),
    (Selection("AH", "H", -0.25), (0, 0), Result.HALF_LOST),
    (Selection("AH", "A", 0.25), (0, 0), Result.HALF_WON),
    (Selection("AH", "A", 1.5), (2, 1), Result.WON),
    (Selection("OU", "O", 2.5), (2, 1), Result.WON),
    (Selection("OU", "U", 2.5), (2, 1), Result.LOST),
    (Selection("OU", "O", 3.0), (2, 1), Result.VOID),
    (Selection("OU", "O", 2.75), (2, 1), Result.HALF_WON),
    (Selection("OU", "U", 2.25), (1, 0), Result.WON),
    (Selection("OU", "U", 2.25), (1, 1), Result.HALF_WON),
    (Selection("OU", "O", 2.25), (1, 1), Result.HALF_LOST),
    (Selection("OU", "U", 2.25), (2, 1), Result.LOST),
    (Selection("BTTS", "Y"), (1, 1), Result.WON),
    (Selection("BTTS", "N"), (1, 0), Result.WON),
    (Selection("TT_H", "O", 1.5), (2, 0), Result.WON),
    (Selection("TT_A", "U", 0.5), (2, 0), Result.WON),
])
def test_settlement(sel, score, expected):
    assert settle(sel, MatchStats(*score)) == expected


def test_first_half_uses_ht_score_and_requires_data():
    assert settle(Selection("1H_OU", "O", 0.5), MatchStats(3, 0)) is None
    assert settle(Selection("1H_OU", "O", 0.5), MatchStats(3, 0, 0, 0)) == Result.LOST
    assert settle(Selection("1H_1X2", "H"), MatchStats(1, 2, 1, 0)) == Result.WON


def test_cards_need_data():
    assert settle(Selection("CARDS_OU", "O", 4.5), MatchStats(0, 0)) is None
    assert settle(Selection("CARDS_OU", "O", 4.5), MatchStats(0, 0, cards=5)) == Result.WON


def test_payout_factors():
    assert payout_factor(Result.WON, 2.0) == 2.0
    assert payout_factor(Result.HALF_WON, 2.0) == 1.5
    assert payout_factor(Result.HALF_LOST, 2.0) == 0.5
    assert payout_factor(Result.VOID, 2.0) == 1.0
    assert payout_factor(Result.LOST, 2.0) == 0.0


def test_match_winner_never_marked_lost_while_live():
    """Krav: ikke merk kampvinner tapt fordi laget ligger under."""
    for score in [(0, 3), (0, 5)]:
        assert live_state(Selection("1X2", "H"), MatchStats(*score)) == LiveState.LIVE
        assert live_state(Selection("AH", "H", -1.5), MatchStats(*score)) == LiveState.LIVE
        assert live_state(Selection("DC", "1X"), MatchStats(*score)) == LiveState.LIVE


def test_monotone_markets_can_look_decided():
    assert live_state(Selection("OU", "O", 2.5), MatchStats(2, 1)) == LiveState.LIKELY_WON
    assert live_state(Selection("OU", "U", 2.5), MatchStats(2, 1)) == LiveState.LIKELY_LOST
    assert live_state(Selection("OU", "O", 2.5), MatchStats(1, 1)) == LiveState.LIVE
    assert live_state(Selection("BTTS", "N"), MatchStats(1, 1)) == LiveState.LIKELY_LOST
    assert live_state(Selection("OU", "O", 2.75), MatchStats(2, 1)) == LiveState.LIVE  # halv gevinst kan bli hel


def test_probability_helpers():
    assert implied(2.0) == 0.5
    with pytest.raises(ValueError):
        implied(1.0)
    odds = [1.9, 3.6, 4.2]
    for f in (devig_power, devig_proportional):
        p = f(odds)
        assert abs(sum(p) - 1) < 1e-9
        assert all(0 < x < 1 for x in p)
    pw, pp = devig_power(odds), devig_proportional(odds)
    assert pw[0] > pp[0]  # power-metoden legger mer margin på underdogen
    assert abs(expected_value(0.55, 2.0) - 0.10) < 1e-12
