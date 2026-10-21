"""Performance statistics with uncertainty.

Trades overlap in time and cluster by week, so inference is done on WEEKLY sums of R
(trades grouped by exit week): the t-statistic, the stationary block bootstrap and the Deflated
Sharpe Ratio all use that weekly series.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


def filled(trades: pd.DataFrame) -> pd.DataFrame:
    return trades[trades["status"] == "filled"].copy()


def weekly_r(tr: pd.DataFrame, col: str = "r_net") -> pd.Series:
    t = pd.DatetimeIndex(tr["exit_time"])
    wk = (t - pd.to_timedelta(t.dayofweek, unit="D")).normalize()
    return tr[col].groupby(wk).sum().sort_index()


def max_drawdown(equity: np.ndarray) -> tuple[float, int, int]:
    """Max drawdown (fraction of peak) and its peak/trough indices."""
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1
    j = int(np.argmin(dd))
    i = int(np.argmax(equity[: j + 1])) if j > 0 else 0
    return float(-dd[j]), i, j


def longest_recovery_days(times: pd.DatetimeIndex, equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    under = equity < peak - 1e-12
    best, start = 0.0, None
    for k, u in enumerate(under):
        if u and start is None:
            start = times[k - 1] if k > 0 else times[k]
        if not u and start is not None:
            best = max(best, (times[k] - start).total_seconds() / 86400)
            start = None
    if start is not None:
        best = max(best, (times[-1] - start).total_seconds() / 86400)
    return best


def max_consecutive_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def stationary_bootstrap_mean_ci(x: np.ndarray, denom: np.ndarray | None = None, n_boot: int = 2000,
                                 mean_block: float = 4.0, alpha: float = 0.10, seed: int = 7) -> tuple[float, float]:
    """Politis-Romano stationary bootstrap CI for sum(x)/sum(denom) (ratio of weekly sums)."""
    rng = np.random.default_rng(seed)
    n = len(x)
    if n < 5:
        return (float("nan"), float("nan"))
    d = np.ones(n) if denom is None else denom
    p = 1.0 / mean_block
    est = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.empty(n, int)
        i = rng.integers(n)
        for k in range(n):
            if k > 0 and rng.random() < p:
                i = rng.integers(n)
            elif k > 0:
                i = (i + 1) % n
            idx[k] = i
        dd = d[idx].sum()
        est[b] = x[idx].sum() / dd if dd else np.nan
    return float(np.nanquantile(est, alpha / 2)), float(np.nanquantile(est, 1 - alpha / 2))


def deflated_sharpe(sr: float, n_obs: int, n_trials: int, sr_var_trials: float, skew: float, kurt: float) -> float:
    """Probability that the true Sharpe exceeds the expected max of `n_trials` null Sharpes.

    Bailey & Lopez de Prado (2014). `sr` and `sr_var_trials` are per-period (weekly) Sharpes;
    `kurt` is the (non-excess) kurtosis of the weekly returns.
    """
    if n_obs < 10 or n_trials < 1:
        return float("nan")
    emc = 0.5772156649
    if n_trials == 1:
        sr0 = 0.0
    else:
        sd = math.sqrt(max(sr_var_trials, 1e-12))
        sr0 = sd * ((1 - emc) * stats.norm.ppf(1 - 1 / n_trials) + emc * stats.norm.ppf(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(n_obs - 1) / denom))


def summarize(trades: pd.DataFrame, risk_pct: float = 0.5, boot: bool = True) -> dict:
    allt = trades
    tr = filled(trades).sort_values("exit_time")
    n_sig = int(len(allt))
    out: dict = {"signals": n_sig, "filled": int(len(tr))}
    st = allt["status"].value_counts().to_dict()
    out["status_counts"] = {k: int(v) for k, v in st.items()}
    if len(tr) == 0:
        return out
    r = tr["r_net"].to_numpy(float)
    wins, losses = r[r > 0], r[r <= 0]
    wk = weekly_r(tr)
    wk_n = weekly_r(tr.assign(one=1.0), "one")
    mean_w = wk.mean()
    sd_w = wk.std(ddof=1)
    t_stat = float(mean_w / sd_w * math.sqrt(len(wk))) if sd_w > 0 else float("nan")
    eq = np.cumprod(1 + r * risk_pct / 100)
    mdd, _, _ = max_drawdown(np.concatenate([[1.0], eq]))
    times = pd.DatetimeIndex(tr["exit_time"])
    span_years = max((times[-1] - times[0]).total_seconds() / (365.25 * 86400), 1e-9)
    sr_w = float(mean_w / sd_w) if sd_w > 0 else float("nan")
    out.update(
        expectancy_r=float(r.mean()),
        expectancy_gross_r=float(tr["r_gross"].mean()),
        median_r=float(np.median(r)),
        pips_per_trade=float(tr["pips_net"].mean()),
        win_rate=float((r > 0).mean()),
        avg_win_r=float(wins.mean()) if len(wins) else 0.0,
        avg_loss_r=float(losses.mean()) if len(losses) else 0.0,
        profit_factor=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        total_r=float(r.sum()),
        t_stat_weekly=t_stat,
        weeks=int(len(wk)),
        sharpe_weekly=sr_w,
        sharpe_annual=sr_w * math.sqrt(52) if not math.isnan(sr_w) else float("nan"),
        skew_weekly=float(stats.skew(wk)) if len(wk) > 3 else float("nan"),
        kurt_weekly=float(stats.kurtosis(wk, fisher=False)) if len(wk) > 3 else float("nan"),
        max_dd_pct=100 * mdd,
        cagr_pct=100 * (max(eq[-1], 0.0) ** (1 / span_years) - 1),
        longest_recovery_days=longest_recovery_days(pd.DatetimeIndex([times[0]]).append(times),
                                                    np.concatenate([[1.0], eq])),
        max_consec_losses=max_consecutive_losses(r),
        worst_trade_r=float(r.min()),
        trades_per_month=float(len(tr) / (span_years * 12)),
        avg_hold_h=float(((pd.to_datetime(tr["exit_time"]) - pd.to_datetime(tr["entry_time"])).dt.total_seconds()
                          / 3600).mean()),
        avg_cost_r=float(tr["cost_r"].mean()),
        missed_rate=float(allt["status"].isin(["missed_chase", "missed_zone", "missed_closed", "missed_beyond_stop"]).mean()),
        exit_reasons={k: int(v) for k, v in tr["exit_reason"].value_counts().items()},
    )
    if boot:
        lo, hi = stationary_bootstrap_mean_ci(wk.to_numpy(), wk_n.reindex(wk.index).to_numpy())
        out["expectancy_ci90"] = [lo, hi]
    return out


def by_group(trades: pd.DataFrame, key: pd.Series | str) -> pd.DataFrame:
    tr = filled(trades)
    g = tr.groupby(key if isinstance(key, str) else key.reindex(tr.index))
    return pd.DataFrame({"n": g["r_net"].size(), "exp_r": g["r_net"].mean(), "win": g["r_net"].apply(lambda x: (x > 0).mean()),
                         "total_r": g["r_net"].sum()})
