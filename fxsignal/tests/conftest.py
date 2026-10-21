import numpy as np
import pandas as pd
import pytest

from fxsignal.data.resample import resample
from fxsignal.timeutil import market_open


def synthetic_m15(n_days=400, seed=1, start="2019-01-06 22:00"):
    """Random-walk BID bars with realistic weekend closures (no real market data)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n_days * 96, freq="15min", tz="UTC")
    idx = idx[[market_open(t.to_pydatetime()) for t in idx]]
    vol = 0.0006 * (1 + 0.5 * np.sin(np.arange(len(idx)) / 900))
    r = rng.standard_t(4, len(idx)) * vol / np.sqrt(2)
    c = 1.10 * np.exp(np.cumsum(r))
    o = np.concatenate([[1.10], c[:-1]])
    spread = np.abs(rng.normal(0, vol, len(idx))) * c
    h = np.maximum(o, c) + spread
    l = np.minimum(o, c) - spread
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "tick_volume": 1.0}, index=idx)
    df.attrs["symbol"] = "EURUSD"
    return df


@pytest.fixture(scope="session")
def m15():
    return synthetic_m15()


@pytest.fixture(scope="session")
def h1(m15):
    return resample(m15, "H1")
