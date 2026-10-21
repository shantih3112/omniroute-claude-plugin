"""Forward paper tracking must reproduce the research engine's outcomes bar for bar."""
import numpy as np
import pandas as pd
import pytest

from fxsignal.backtest.engine import BASE, ExecSeries, simulate
from fxsignal.instruments import get
from fxsignal.signals.lifecycle import Bar, PaperTracker
from conftest import synthetic_m15


def m1_series(days=30, seed=3):
    m15 = synthetic_m15(n_days=days, seed=seed)
    # build M1 by splitting each M15 bar into 15 flat-ish minutes (deterministic path)
    rows = []
    for t, r in m15.iterrows():
        path = np.linspace(r.open, r.close, 15)
        for k in range(15):
            o = path[k - 1] if k else r.open
            c = path[k]
            h = max(o, c) + (r.high - max(r.open, r.close)) * (k == 7)
            l = min(o, c) - (min(r.open, r.close) - r.low) * (k == 3)
            rows.append((t + pd.Timedelta(minutes=k), o, h, l, c))
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"]).set_index("time")
    df["tick_volume"] = 1.0
    return df


@pytest.mark.parametrize("seed", [3, 4])
def test_tracker_matches_engine(seed):
    m1 = m1_series(seed=seed)
    inst = get("EURUSD")
    rng = np.random.default_rng(seed)
    times = m1.index[rng.choice(np.arange(200, len(m1) - 3000), 40, replace=False)]
    sigs = []
    for k, t in enumerate(sorted(times)):
        side = 1 if rng.random() < 0.5 else -1
        dist = 0.0015
        # every 4th signal has a stale reference so the follower is outside the entry zone
        ref = m1.loc[t, "close"] + (side * (-0.0006 if k % 8 == 0 else 0.0012) if k % 4 == 0 else 0.0)
        sigs.append(dict(time=t + pd.Timedelta(minutes=1), side=side, entry_type="market", entry_ref=ref,
                         stop=ref - side * dist, target=ref + side * 2 * dist,
                         max_hold_min=60 if k % 3 == 0 else 600, expiry_min=30,
                         atr=dist, regime="", note=""))
    sdf = pd.DataFrame(sigs)
    eng = simulate(sdf, ExecSeries(m1, 1), inst, BASE, delay_min=1, one_at_a_time=False)
    seen = set(eng["status"]) | set(eng["exit_reason"].dropna())
    assert {"filled", "time", "stop"} <= seen and seen & {"missed_chase", "missed_zone"}, seen
    tracker = PaperTracker(inst, BASE, paper_delay_min=1)
    for i, s in enumerate(sigs):
        sig = dict(id=str(i), side=s["side"], entry_ref=s["entry_ref"], stop=s["stop"], target=s["target"],
                   max_hold_min=s["max_hold_min"], created_at=s["time"],
                   expires_at=s["time"] + pd.Timedelta(minutes=s["expiry_min"]))
        st, out = {}, []
        for t, r in m1[m1.index >= s["time"]].iterrows():
            st, trs = tracker.step(sig, st, Bar(t, r.open, r.high, r.low, r.close))
            out += trs
            if st.get("phase") == "done":
                break
        e = eng.iloc[i]
        kinds = [x.kind for x in out]
        if e.status == "filled":
            assert kinds[-1] == "closed", (i, e.status, kinds)
            assert out[-1].r_result == pytest.approx(e.r_net, abs=1e-9)
            assert out[-1].detail["reason"] == e.exit_reason
        elif e.status in ("missed_chase", "missed_zone", "missed_beyond_stop"):
            assert kinds == ["missed"]
        else:
            assert kinds in (["expired"], []), (e.status, kinds)
