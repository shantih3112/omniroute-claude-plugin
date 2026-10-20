import numpy as np
import pandas as pd
import pytest

from fxsignal.backtest.engine import ZERO, CostScenario, ExecSeries, simulate
from fxsignal.instruments import Instrument

INST = Instrument("TESTUSD", "TES", "USD", 0.0001, 5, spread_pips=1.0, commission_usd_per_lot_side=0.0,
                  swap_pips_per_night=0.0)
SPREAD_ONLY = CostScenario("spread", 1.0, 0.0, 0.0, 0.0, 0.0)


def bars(rows, start="2024-01-02 12:00", tf="15min"):
    idx = pd.date_range(start, periods=len(rows), freq=tf, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(tick_volume=1.0)


def sig(time, side, ref, stop, target, hold=600, expiry=60, etype="market"):
    return pd.DataFrame([dict(time=pd.Timestamp(time, tz="UTC"), side=side, entry_type=etype, entry_ref=ref,
                              stop=stop, target=target, max_hold_min=hold, expiry_min=expiry, atr=0.001,
                              regime="", note="")])


def test_long_target_hit_zero_cost():
    df = bars([(1.1000, 1.1005, 1.0995, 1.1000), (1.1000, 1.1030, 1.0995, 1.1025)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1020), ExecSeries(df, 15), INST, ZERO)
    r = t.iloc[0]
    assert r.status == "filled" and r.exit_reason == "target"
    assert r.entry == pytest.approx(1.1000) and r.r_net == pytest.approx(1.0)


def test_stop_wins_when_both_touched_in_same_bar():
    df = bars([(1.1000, 1.1030, 1.0970, 1.1000)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1020), ExecSeries(df, 15), INST, ZERO)
    assert t.iloc[0].exit_reason == "stop" and t.iloc[0].r_net == pytest.approx(-1.0)


def test_gap_through_stop_fills_at_open():
    df = bars([(1.1000, 1.1005, 1.0990, 1.0990), (1.0950, 1.0960, 1.0940, 1.0950)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1100), ExecSeries(df, 15), INST, ZERO)
    r = t.iloc[0]
    assert r.exit_reason == "stop" and r.exit == pytest.approx(1.0950)
    assert r.r_net == pytest.approx(-2.5)  # worse than -1R: stops do not guarantee price


def test_short_uses_ask_for_stop_and_spread_costs():
    # bid high 1.1015 + 1 pip spread = 1.1016 ask -> stop at 1.1015 is hit
    df = bars([(1.1000, 1.1015, 1.0995, 1.1000)])
    t = simulate(sig("2024-01-02 12:00", -1, 1.1000, 1.1015, 1.0950), ExecSeries(df, 15), INST, SPREAD_ONLY)
    r = t.iloc[0]
    assert r.exit_reason == "stop"
    assert r.entry == pytest.approx(1.1000)  # short sells at bid
    assert r.r_net == pytest.approx(-1.0)


def test_long_pays_spread_on_entry():
    df = bars([(1.1000, 1.1005, 1.0999, 1.1000), (1.1000, 1.1100, 1.0999, 1.1100)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1020), ExecSeries(df, 15), INST, SPREAD_ONLY)
    r = t.iloc[0]
    assert r.entry == pytest.approx(1.1001)
    assert r.r_net == pytest.approx((1.1020 - 1.1001) / (1.1001 - 1.0980))


def test_delay_skips_to_later_bar_and_chase_rule():
    # by the time the follower acts (30 min later) price moved 15 pips up: 0.75R adverse > 0.25R
    df = bars([(1.1000, 1.1005, 1.0999, 1.1003), (1.1003, 1.1010, 1.1001, 1.1009), (1.1015, 1.1020, 1.1010, 1.1015)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1040), ExecSeries(df, 15), INST, ZERO, delay_min=30)
    assert t.iloc[0].status == "missed_chase"


def test_time_stop_and_no_lookahead_into_signal_bar():
    df = bars([(1.1000, 1.1001, 1.0999, 1.1000)] * 10)
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1100, hold=60), ExecSeries(df, 15), INST, ZERO)
    r = t.iloc[0]
    assert r.exit_reason == "time"
    assert pd.Timestamp(r.entry_time) == pd.Timestamp("2024-01-02 12:00", tz="UTC")
    assert pd.Timestamp(r.exit_time) == pd.Timestamp("2024-01-02 13:00", tz="UTC")


def test_signal_expires_over_weekend():
    df = bars([(1.1, 1.1, 1.1, 1.1)], start="2024-01-08 00:00")
    t = simulate(sig("2024-01-05 21:00", 1, 1.1, 1.09, 1.12, expiry=60), ExecSeries(df, 15), INST, ZERO)
    assert t.iloc[0].status == "missed_closed"


def test_limit_entry_fills_only_when_traded_through():
    df = bars([(1.1010, 1.1015, 1.1006, 1.1008), (1.1008, 1.1009, 1.1003, 1.1005), (1.1005, 1.1040, 1.1004, 1.1040)])
    s = sig("2024-01-02 12:00", 1, 1.1004, 1.0990, 1.1030, etype="limit")
    t = simulate(s, ExecSeries(df, 15), INST, SPREAD_ONLY)
    r = t.iloc[0]  # bar 2: bid low 1.1003 + 1 pip spread = 1.1004 ask -> fills
    assert r.status == "filled" and r.entry == pytest.approx(1.1004) and r.exit_reason == "target"


def test_trailing_stop_ratchets_only_after_publication():
    df = bars([(1.1000, 1.1010, 1.0999, 1.1010), (1.1010, 1.1030, 1.1009, 1.1030), (1.1030, 1.1031, 1.1012, 1.1015)])
    trail = pd.DataFrame({"long_trail": [1.1015], "short_trail": [np.nan]},
                         index=[pd.Timestamp("2024-01-02 12:30", tz="UTC")])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, np.nan), ExecSeries(df, 15), INST, ZERO, trail=trail)
    r = t.iloc[0]
    assert r.exit_reason == "trail" and r.exit == pytest.approx(1.1015)


def test_one_at_a_time():
    df = bars([(1.1000, 1.1001, 1.0999, 1.1000)] * 20)
    s = pd.concat([sig("2024-01-02 12:00", 1, 1.1, 1.09, 1.12, hold=120),
                   sig("2024-01-02 12:30", 1, 1.1, 1.09, 1.12, hold=120)], ignore_index=True)
    t = simulate(s, ExecSeries(df, 15), INST, ZERO)
    assert list(t.status) == ["filled", "skipped_open"]


def test_entry_zone_is_two_sided_and_r_uses_planned_risk():
    # price fell 15 pips toward the stop before the follower could act: outside the zone
    df = bars([(1.1000, 1.1001, 1.0985, 1.0986), (1.0985, 1.0990, 1.0984, 1.0988)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1040), ExecSeries(df, 15), INST, ZERO, delay_min=15)
    assert t.iloc[0].status == "missed_zone"
    # a small favourable drift is accepted, and losses are measured against the planned risk
    df = bars([(1.1000, 1.1001, 1.0995, 1.0996), (1.0996, 1.0997, 1.0970, 1.0975)])
    t = simulate(sig("2024-01-02 12:00", 1, 1.1000, 1.0980, 1.1040), ExecSeries(df, 15), INST, ZERO, delay_min=15)
    r = t.iloc[0]
    assert r.status == "filled" and r.r_net == pytest.approx((1.0980 - 1.0996) / 0.0020)


def test_trade_spanning_vendor_hole_is_not_scored():
    a = bars([(1.1000, 1.1001, 1.0999, 1.1000)] * 4, start="2024-01-09 12:00")
    b = bars([(1.0500, 1.0501, 1.0499, 1.0500)] * 4, start="2024-01-10 12:00")  # 23h missing midweek
    t = simulate(sig("2024-01-09 12:00", 1, 1.1000, 1.0980, 1.1100, hold=5000), ExecSeries(pd.concat([a, b]), 15),
                 INST, ZERO)
    assert t.iloc[0].status == "data_gap"


def test_weekend_gap_is_not_a_hole():
    a = bars([(1.1000, 1.1001, 1.0999, 1.1000)] * 2, start="2024-01-05 21:00")  # Friday close
    b = bars([(1.0950, 1.0951, 1.0949, 1.0950)] * 2, start="2024-01-07 22:00")  # Sunday open, gap down
    t = simulate(sig("2024-01-05 21:00", 1, 1.1000, 1.0980, 1.1100, hold=5000), ExecSeries(pd.concat([a, b]), 15),
                 INST, ZERO)
    assert t.iloc[0].status == "filled" and t.iloc[0].exit == pytest.approx(1.0950)  # weekend gap risk is real
