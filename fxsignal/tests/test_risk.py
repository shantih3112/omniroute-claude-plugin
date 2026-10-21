from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fxsignal.instruments import get
from fxsignal.risk.engine import OpenRisk, PortfolioState, Proposal, RiskConfig, RiskEngine, currency_exposure
from fxsignal.risk.ftmo import FtmoProfile, check_equity, floors, prague_day, simulate_challenge
from fxsignal.risk.sizing import convert, size_position

PRICES = {"EURUSD": 1.10, "USDJPY": 150.0, "GBPUSD": 1.30, "USDNOK": 10.5, "EURNOK": 11.55, "USDCHF": 0.9}
ROOT = Path(__file__).resolve().parents[1]


# ---- sizing --------------------------------------------------------------------------------
def test_size_eurusd_usd_account():
    # 10,000 USD, 0.5% = 50 USD; 20-pip stop = 200 USD/lot + 5 USD commission -> 0.24 lots
    r = size_position(get("EURUSD"), 10_000, "USD", 0.5, 1.1000, 1.0980, PRICES)
    assert r.ok and r.lots == pytest.approx(0.24)
    assert r.risk_amount <= 50.0 + 1e-9


def test_size_never_rounds_up_to_min_lot():
    # 500 USD account, 0.5% = 2.5 USD; 1 micro lot on a 30-pip stop = 3 USD + comm -> refuse
    r = size_position(get("EURUSD"), 500, "USD", 0.5, 1.1000, 1.0970, PRICES)
    assert not r.ok and "never round up" in r.reason


def test_size_jpy_pair_converts_quote_currency():
    # USDJPY 50-pip (0.50) stop: per lot 0.5*100000 JPY = 50,000 JPY = 333.33 USD (+5 comm)
    r = size_position(get("USDJPY"), 100_000, "USD", 0.5, 150.00, 149.50, PRICES)
    assert r.ok and r.loss_per_lot == pytest.approx(50_000 / 150 + 5, rel=1e-6)
    assert r.lots == pytest.approx(np.floor(500 / (50_000 / 150 + 5) * 100) / 100)


def test_size_nok_account_via_triangulation():
    v = convert(100.0, "GBP", "NOK", PRICES)
    assert v == pytest.approx(100 * 1.30 * 10.5)
    r = size_position(get("GBPUSD"), 100_000, "NOK", 0.5, 1.3000, 1.2950, PRICES)
    assert r.ok and r.risk_amount <= 500.0


def test_size_margin_check():
    r = size_position(get("EURUSD"), 10_000, "USD", 1.0, 1.1000, 1.0999, PRICES, free_margin=100.0)
    assert not r.ok and "margin" in r.reason


# ---- risk engine ---------------------------------------------------------------------------
def prop(sym="EURUSD", side=1, entry=1.1, stop=1.098, target=1.104, spread=0.4, age=5):
    return Proposal("S1", sym, side, entry, stop, target, spread, age)


def test_engine_approves_clean_proposal(tmp_path):
    eng = RiskEngine(RiskConfig(), tmp_path)
    d = eng.evaluate(prop(), get("EURUSD"), PortfolioState())
    assert d.approved and d.risk_pct == 0.5


def test_kill_switch_blocks(tmp_path):
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / "KILL_SWITCH").write_text("x")
    d = RiskEngine(RiskConfig(), tmp_path).evaluate(prop(), get("EURUSD"), PortfolioState())
    assert not d.approved and "kill switch" in d.reasons[0]


def test_currency_exposure_blocks_same_usd_bet(tmp_path):
    st = PortfolioState(open=[OpenRisk("A", "GBPUSD", 1, 0.5, "GBP", "USD"), OpenRisk("B", "AUDUSD", 1, 0.5, "AUD", "USD")])
    d = RiskEngine(RiskConfig(), tmp_path).evaluate(prop(), get("EURUSD"), st)
    assert not d.approved and any("USD net exposure" in r for r in d.reasons)
    assert currency_exposure(st.open)["USD"] == pytest.approx(-1.0)


def test_correlation_blocks_duplicate_bet(tmp_path):
    st = PortfolioState(open=[OpenRisk("A", "GBPUSD", 1, 0.5, "GBP", "USD")])
    d = RiskEngine(RiskConfig(max_currency_exposure_pct=5), tmp_path).evaluate(
        prop(), get("EURUSD"), st, corr={("EURUSD", "GBPUSD"): 0.8})
    assert not d.approved and any("same bet" in r for r in d.reasons)
    # opposite direction on a positively correlated pair is a hedge, not a duplicate
    d2 = RiskEngine(RiskConfig(max_currency_exposure_pct=5), tmp_path).evaluate(
        prop(side=-1, stop=1.102, target=1.096), get("EURUSD"), st, corr={("EURUSD", "GBPUSD"): 0.8})
    assert not any("same bet" in r for r in d2.reasons)


def test_losing_streak_only_reduces_risk(tmp_path):
    eng = RiskEngine(RiskConfig(), tmp_path)
    assert eng.risk_for_next_trade(PortfolioState(consecutive_losses=5)) == 0.25
    assert not eng.evaluate(prop(), get("EURUSD"), PortfolioState(consecutive_losses=6)).approved
    with pytest.raises(ValueError):
        RiskConfig(losing_streak_risk_scale=2.0)  # martingale-style scaling is impossible
    with pytest.raises(ValueError):
        RiskConfig(risk_per_trade_pct=2.0)


def test_daily_and_overall_stops(tmp_path):
    eng = RiskEngine(RiskConfig(), tmp_path)
    assert not eng.evaluate(prop(), get("EURUSD"), PortfolioState(equity_pct=96.9, day_start_equity_pct=99.9)).approved
    assert not eng.evaluate(prop(), get("EURUSD"), PortfolioState(equity_pct=92, peak_equity_pct=100,
                                                                  day_start_equity_pct=92)).approved


def test_spread_stale_rr_and_open_risk(tmp_path):
    eng = RiskEngine(RiskConfig(), tmp_path)
    assert not eng.evaluate(prop(spread=5), get("EURUSD"), PortfolioState()).approved
    assert not eng.evaluate(prop(age=900), get("EURUSD"), PortfolioState()).approved
    assert not eng.evaluate(prop(target=1.1015), get("EURUSD"), PortfolioState()).approved  # 0.75R
    st = PortfolioState(open=[OpenRisk(str(i), s, 1, 0.5, s[:3], s[3:]) for i, s in
                              enumerate(["USDJPY", "AUDJPY", "EURCHF", "GBPJPY"])])
    d = eng.evaluate(prop(), get("EURUSD"), st)
    assert any("open risk" in r for r in d.reasons)


# ---- FTMO -------------------------------------------------------------------------------------
@pytest.fixture
def prof():
    return FtmoProfile.load(ROOT / "config" / "ftmo" / "2step_standard_phase1.yaml")


def test_profile_unverified_blocks_challenge(prof):
    ok, why = prof.challenge_use_allowed()
    assert not ok and "UNVERIFIED" in why


def test_daily_floor_exact_boundary(prof):
    d, o = floors(prof, 10_400, 10_400)
    assert d == pytest.approx(9_900) and o == pytest.approx(9_000)
    assert not check_equity(prof, 9_900.01, 10_400, 10_400).breached
    assert check_equity(prof, 9_900.0, 10_400, 10_400).breached  # touching the floor breaches
    assert check_equity(prof, 8_999, 9_100, 9_100).reason == "max loss"


def test_prague_midnight_reset_across_dst():
    # 21:59 and 22:01 UTC in summer straddle Prague midnight (UTC+2); in winter it is 23:00 UTC
    s = pd.to_datetime(pd.Series(["2024-07-01 21:59", "2024-07-01 22:01", "2024-12-02 22:59", "2024-12-02 23:01",
                                  "2024-10-26 21:59", "2024-10-27 23:30"]), utc=True)
    d = prague_day(s).dt.strftime("%Y-%m-%d").tolist()
    assert d == ["2024-07-01", "2024-07-02", "2024-12-02", "2024-12-03", "2024-10-26", "2024-10-28"]


def _trades(rows):
    df = pd.DataFrame(rows, columns=["entry_time", "exit_time", "r_net", "mae_r"])
    df["status"] = "filled"
    for c in ("entry_time", "exit_time"):
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def test_challenge_pass_needs_min_trading_days(prof):
    # +2R per trade at 1% = +2% per trade; 5 trades on 5 days -> +10% after the 5th, 5 trading days
    rows = [(f"2024-03-0{d} 09:00", f"2024-03-0{d} 15:00", 2.0, -0.2) for d in range(4, 9)]
    r = simulate_challenge(_trades(rows), prof, 1.0, pd.Timestamp("2024-03-01", tz="UTC"))
    assert r["result"] == "pass" and r["trading_days"] >= 4


def test_challenge_floating_loss_breaches_daily_limit(prof):
    # a single trade that closes as a small loss but whose MAE hit -5.1R at 1% = -5.1% intraday
    r = simulate_challenge(_trades([("2024-03-04 09:00", "2024-03-04 15:00", -0.5, -5.1)]), prof, 1.0,
                           pd.Timestamp("2024-03-01", tz="UTC"))
    assert r["result"] == "breach_max_daily_loss"


def test_position_carried_across_reset_counts_on_both_days(prof):
    # opened Monday 20:00 UTC, closes Tuesday after Prague midnight; MAE counted on both days
    t = _trades([("2024-03-04 20:00", "2024-03-05 08:00", -1.0, -1.0)])
    r = simulate_challenge(t, prof, 1.0, pd.Timestamp("2024-03-01", tz="UTC"))
    assert r["result"] == "incomplete" and r["final_pct"] == pytest.approx(-1.0)
