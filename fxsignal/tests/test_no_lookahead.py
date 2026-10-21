"""Truncation invariance: a signal decided at time T must be identical whether the strategy sees
data up to T or the whole history. Any use of future bars (including partially formed
higher-timeframe bars) breaks this."""
import numpy as np
import pandas as pd
import pytest

from fxsignal import features as F
from fxsignal.data.resample import align_to, resample
from fxsignal.strategies.library import GRIDS, REGISTRY

STRATS = [(name, cfg) for name, cfgs in GRIDS.items() for cfg in cfgs[:1]] + [("random", {})]


def _input(name, m15, h1):
    return m15 if REGISTRY[name]().signal_tf == "M15" else h1


@pytest.mark.parametrize("name,cfg", STRATS)
def test_truncation_invariance(name, cfg, m15, h1):
    data = _input(name, m15, h1)
    full = REGISTRY[name](**cfg).generate(data)
    assert len(full) > 0, f"{name} produced no signals on synthetic data"
    cut_points = data.index[np.linspace(len(data) // 3, len(data) - 5, 6).astype(int)]
    cols = ["side", "entry_ref", "stop", "target", "max_hold_min"]
    for cut in cut_points:
        part = data[data.index <= cut]
        decided_by = cut + (part.index[-1] - part.index[-2])  # close of the last included bar
        trunc = REGISTRY[name](**cfg).generate(part)
        a = full[full["time"] <= decided_by].reset_index(drop=True)
        b = trunc[trunc["time"] <= decided_by].reset_index(drop=True)
        assert list(a["time"]) == list(b["time"]), f"{name}: signal times differ at cut {cut}"
        np.testing.assert_allclose(a[cols].to_numpy(float), b[cols].to_numpy(float), rtol=1e-9, atol=1e-12,
                                   equal_nan=True)


def test_signal_time_is_after_bar_close(h1):
    s = REGISTRY["trend_pullback"]().generate(h1)
    bar_opens = set(h1.index)
    assert all((t - pd.Timedelta(hours=1)) in bar_opens for t in s["time"])


def test_align_to_never_uses_unclosed_htf_bar(h1):
    d = resample(h1, "D1")
    feat = pd.DataFrame({"dclose": d["close"]})
    al = align_to(h1, "H1", feat, "D1")
    d_close_time = d.index + pd.Timedelta(days=1)
    for t in h1.index[::97][5:]:
        val = al.loc[t, "dclose"]
        if np.isnan(val):
            continue
        k = np.flatnonzero(d["close"].to_numpy() == val)[-1]
        assert d_close_time[k] <= t + pd.Timedelta(hours=1)


def test_features_causal(h1):
    cut = h1.index[len(h1) // 2]
    part = h1[h1.index <= cut]
    for fn in (lambda x: F.atr(x, 14), lambda x: F.adx(x, 14), lambda x: F.rsi(x["close"], 14),
               lambda x: F.prior_high(x, 20), lambda x: F.rolling_pct_rank(F.atr(x, 14), 200),
               lambda x: F.bollinger(x["close"])[0], lambda x: F.efficiency_ratio(x["close"], 20)):
        a, b = fn(h1).loc[:cut], fn(part)
        np.testing.assert_allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True, rtol=1e-9)


def test_d1_bars_are_ny_close_aligned(h1):
    d = resample(h1, "D1")
    ny = d.index.tz_convert("America/New_York")
    assert set(ny.hour) == {17} and set(ny.minute) == {0}
    assert 5 not in set((d.index + pd.Timedelta(hours=7)).tz_convert("America/New_York").dayofweek)
