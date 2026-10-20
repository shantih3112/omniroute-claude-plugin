"""Bar-by-bar Python port of src/core.pine (confirmed-bar logic only).

Purpose: an independent, reproducible offline check of the signal logic on real
public OHLC data, because TradingView's Strategy Tester was not reachable from
the build environment. Differences from Pine are listed in docs/BACKTESTING.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ───────────────────────── Pine-equivalent indicators ─────────────────────────

def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    s = pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()
    out[:] = s
    return out


def _seeded(x: np.ndarray, n: int, alpha: float) -> np.ndarray:
    """Pine ema/rma: seeded with the SMA of the first n valid values."""
    out = np.full(len(x), np.nan)
    valid = np.where(~np.isnan(x))[0]
    if len(valid) < n:
        return out
    start = valid[0] + n - 1
    out[start] = np.mean(x[valid[0]:start + 1])
    for i in range(start + 1, len(x)):
        v = x[i] if not np.isnan(x[i]) else out[i - 1]
        out[i] = alpha * v + (1 - alpha) * out[i - 1]
    return out


def ema(x, n):
    return _seeded(x, n, 2.0 / (n + 1))


def rma(x, n):
    return _seeded(x, n, 1.0 / n)


def true_range(h, l, c):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def dmi(h, l, c, di_len=14, adx_len=14):
    up = np.r_[np.nan, np.diff(h)]
    dn = np.r_[np.nan, -np.diff(l)]
    pdm = np.where(np.isnan(up), np.nan, np.where((up > dn) & (up > 0), up, 0.0))
    mdm = np.where(np.isnan(dn), np.nan, np.where((dn > up) & (dn > 0), dn, 0.0))
    trur = rma(true_range(h, l, c), di_len)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus = 100 * rma(pdm, di_len) / trur
        minus = 100 * rma(mdm, di_len) / trur
        s = plus + minus
        adx = 100 * rma(np.abs(plus - minus) / np.where(s == 0, 1, s), adx_len)
    return plus, minus, adx


def rsi(c, n=14):
    ch = np.r_[np.nan, np.diff(c)]
    up = rma(np.where(np.isnan(ch), np.nan, np.maximum(ch, 0)), n)
    dn = rma(np.where(np.isnan(ch), np.nan, np.maximum(-ch, 0)), n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(dn == 0, 100.0, np.where(up == 0, 0.0, 100 - 100 / (1 + up / dn)))


def stdev_pop(x, n):
    return pd.Series(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()


def percentrank(x, n):
    """Pine ta.percentrank: % of the previous n values that are <= current."""
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        w = x[i - n:i]
        if np.isnan(x[i]) or np.isnan(w).any():
            continue
        out[i] = 100.0 * np.sum(w <= x[i]) / n
    return out


def highest(x, n):
    return pd.Series(x).rolling(n, min_periods=n).max().to_numpy()


def lowest(x, n):
    return pd.Series(x).rolling(n, min_periods=n).min().to_numpy()


def shift(x, k=1):
    return np.r_[np.full(k, np.nan), x[:-k]]


def pivots(h, l, L, R):
    """Value reported on the CONFIRMATION bar (t), for the pivot at t-R."""
    n = len(h)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for t in range(L + R, n):
        c = t - R
        if h[c] > h[c - L:c].max() and h[c] > h[c + 1:t + 1].max():
            ph[t] = h[c]
        if l[c] < l[c - L:c].min() and l[c] < l[c + 1:t + 1].min():
            pl[t] = l[c]
    return ph, pl


# ───────────────────────── Configuration ─────────────────────────

@dataclass
class Cfg:
    asset: str                 # Stock / Forex / Crypto
    htf_rule: str              # pandas resample rule for the higher timeframe
    cost_side: float           # cost per side as a fraction of price (commission+slippage+half-spread)
    leverage: float = 1.0
    baseline: bool = False
    use: dict = field(default_factory=lambda: {"TP": True, "BO": True, "MR": True, "SW": True})
    warmup: int = 250
    pvL: int = 5
    pvR: int = 3
    sqz: float = 20.0
    don: int = 20
    t1R: float = 1.0
    t2R: float = 2.0
    chase: float = 0.25
    expiry: int = 3
    max_hold: int = 40
    reg_exit: bool = True
    short_ok: bool = True
    fx_roll: bool = True

    @property
    def adx_trend(self):
        return 20.0 if self.asset == "Stock" else 22.0

    @property
    def min_stop(self):
        return 1.0 if self.asset == "Crypto" else 0.75

    @property
    def max_stop(self):
        return 3.5 if self.asset == "Crypto" else 3.0


def htf_bias(df: pd.DataFrame, rule: str) -> np.ndarray:
    """Bias of the previous COMPLETED higher-timeframe bar (Pine: f()[1] + lookahead_on)."""
    agg = df.resample(rule, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    c = agg["Close"].to_numpy()
    e20, e50 = ema(c, 20), ema(c, 50)
    b = np.where((c > e20) & (e20 > e50), 1.0, np.where((c < e20) & (e20 < e50), -1.0, 0.0))
    b[np.isnan(e50)] = np.nan
    prev = pd.Series(shift(b, 1), index=agg.index)
    # chart bar belongs to HTF period starting at floor(time); use that period's "prev" value
    period_start = agg.index[np.searchsorted(agg.index, df.index, side="right") - 1]
    return prev.reindex(period_start).to_numpy()


# ───────────────────────── Engine ─────────────────────────

def run(df: pd.DataFrame, cfg: Cfg) -> tuple[pd.DataFrame, dict]:
    o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    v = df["Volume"].to_numpy(float) if "Volume" in df else np.full(len(c), np.nan)
    n = len(c)
    atr = rma(true_range(h, l, c), 14)
    emaF, emaM, emaS = ema(c, 20), ema(c, 50), ema(c, 200)
    diP, diM, adx = dmi(h, l, c)
    rs = rsi(c)
    mid = sma(c, 20)
    sd = stdev_pop(c, 20)
    bbU, bbL = mid + 2 * sd, mid - 2 * sd
    bbwRank = percentrank((bbU - bbL) / mid, 120)
    sqzRecent = shift(lowest(bbwRank, 5)) <= cfg.sqz
    donHi, donLo = shift(highest(h, cfg.don)), shift(lowest(l, cfg.don))
    atrRank = percentrank(atr / c, 100)
    slopeM = (emaM - shift(emaM, 10)) / atr
    lo3, hi3, lo5, hi5 = lowest(l, 3), highest(h, 3), lowest(l, 5), highest(h, 5)
    volOk = np.nansum(v) > 0
    useVol = cfg.asset in ("Stock", "Crypto") and volOk
    volSma = sma(v, 20)
    ph, pl = pivots(h, l, cfg.pvL, cfg.pvR)
    htf = htf_bias(df, cfg.htf_rule)
    adxT, adxR = cfg.adx_trend, cfg.adx_trend - 2
    if cfg.asset == "Forex" and cfg.fx_roll:
        ny = df.index.tz_localize("UTC").tz_convert("America/New_York")
        mins = ny.hour * 60 + ny.minute
        bar_min = int((df.index[1] - df.index[0]).total_seconds() // 60)
        overlap = np.asarray((mins < 17 * 60 + 45) & (mins + bar_min > 16 * 60 + 45))
        roll = overlap if bar_min < 1440 else np.zeros(n, bool)
    else:
        roll = np.zeros(n, bool)

    lastPH = prevPH = lastPL = prevPL = np.nan
    phSwept = plSwept = False
    st = dict(dir=0, state=0, ref=np.nan, lim=np.nan, stop=np.nan, cur=np.nan, t1=np.nan, t2=np.nan,
              fill=np.nan, bar=-1, fillbar=-1, t1hit=False, strat="")
    trades = []
    in_trade = np.zeros(n, bool)
    regime = np.full(n, 2)

    def close_trade(px, kind, i):
        risk = abs(st["fill"] - st["stop"])
        d = st["dir"]
        r2 = d * (px - st["fill"]) / risk
        gross = 0.5 * d * (st["t1"] - st["fill"]) / risk + 0.5 * r2 if st["t1hit"] else r2
        # costs: entry on full size, exits on each half (approximated at their prices)
        cost_px = cfg.cost_side * (st["fill"] + (0.5 * st["t1"] + 0.5 * px if st["t1hit"] else px))
        net = gross - cost_px / risk
        trades.append(dict(sig_bar=st["bar"], sig_time=df.index[st["bar"]], fill_bar=st["fillbar"],
                           exit_bar=i, exit_time=df.index[i], dir=d, strat=st["strat"], kind=kind,
                           R_gross=gross, R_net=net, risk_frac_px=risk / st["fill"]))
        in_trade[st["fillbar"]:i + 1] = True
        st["state"] = 3

    for i in range(1, n):
        # structure (pivot confirmed on this bar)
        if not np.isnan(ph[i]):
            prevPH, lastPH, phSwept = lastPH, ph[i], False
        if not np.isnan(pl[i]):
            prevPL, lastPL, plSwept = lastPL, pl[i], False
        structUp = lastPH > prevPH and lastPL > prevPL
        structDn = lastPH < prevPH and lastPL < prevPL
        if np.isnan(atr[i]) or np.isnan(adx[i]):
            continue
        # int() each term: numpy bool + numpy bool is a logical OR, not a count
        upPts = sum(int(x) for x in (c[i] > emaS[i], emaM[i] > emaS[i], slopeM[i] > 0.2, structUp, diP[i] > diM[i]))
        dnPts = sum(int(x) for x in (c[i] < emaS[i], emaM[i] < emaS[i], slopeM[i] < -0.2, structDn, diM[i] > diP[i]))
        if adx[i] >= adxT and upPts >= 4:
            tr = 1
        elif adx[i] >= adxT and dnPts >= 4:
            tr = -1
        elif adx[i] < adxR and abs(slopeM[i]) < 0.5:
            tr = 0
        else:
            tr = 2
        regime[i] = tr
        hb = htf[i]
        hbL = (not np.isnan(hb)) and hb >= 0
        hbS = (not np.isnan(hb)) and hb <= 0
        a = atr[i]
        volConf = (not useVol) or (v[i] > volSma[i] * 1.2)
        bull, bear = c[i] > o[i], c[i] < o[i]
        rng = h[i] - l[i]
        tpL = tr == 1 and hbL and lo3[i] <= emaF[i] + 0.25 * a and c[i] > emaF[i] and bull and c[i] > h[i - 1] and c[i] - emaF[i] <= a
        tpS = tr == -1 and hbS and hi3[i] >= emaF[i] - 0.25 * a and c[i] < emaF[i] and bear and c[i] < l[i - 1] and emaF[i] - c[i] <= a
        boL = bool(sqzRecent[i]) and c[i] > donHi[i] and bull and rng >= a and tr != -1 and hbL and volConf
        boS = bool(sqzRecent[i]) and c[i] < donLo[i] and bear and rng >= a and tr != 1 and hbS and volConf
        mrL = tr == 0 and hbL and l[i - 1] < bbL[i - 1] and c[i] > bbL[i] and bull and rs[i - 1] < 35
        mrS = tr == 0 and hbS and h[i - 1] > bbU[i - 1] and c[i] < bbU[i] and bear and rs[i - 1] > 65
        swL = (not plSwept) and not np.isnan(lastPL) and l[i] < lastPL and c[i] > lastPL and bull and min(o[i], c[i]) - l[i] >= 0.5 * rng and tr != -1 and hbL
        swS = (not phSwept) and not np.isnan(lastPH) and h[i] > lastPH and c[i] < lastPH and bear and h[i] - max(o[i], c[i]) >= 0.5 * rng and tr != 1 and hbS
        if l[i] < lastPL:
            plSwept = True
        if h[i] > lastPH:
            phSwept = True

        if cfg.baseline:
            sL = "BL" if (emaF[i] > emaM[i] and emaF[i - 1] <= emaM[i - 1]) else ""
            sS = "BL" if (emaF[i] < emaM[i] and emaF[i - 1] >= emaM[i - 1]) else ""
        else:
            u = cfg.use
            sL = "SW" if u["SW"] and swL else "TP" if u["TP"] and tpL else "BO" if u["BO"] and boL else "MR" if u["MR"] and mrL else ""
            sS = "SW" if u["SW"] and swS else "TP" if u["TP"] and tpS else "BO" if u["BO"] and boS else "MR" if u["MR"] and mrS else ""
        rawL = {"SW": l[i] - 0.2 * a, "MR": lo3[i] - 0.2 * a, "BO": (donHi[i] + donLo[i]) / 2}.get(sL, lo5[i] - 0.2 * a)
        rawS = {"SW": h[i] + 0.2 * a, "MR": hi3[i] + 0.2 * a, "BO": (donHi[i] + donLo[i]) / 2}.get(sS, hi5[i] + 0.2 * a)
        dL, dS = c[i] - rawL, rawS - c[i]
        stopL, stopS = c[i] - max(dL, cfg.min_stop * a), c[i] + max(dS, cfg.min_stop * a)

        blocked = (i < cfg.warmup or np.isnan(hb) or atrRank[i] > 95
                   or abs(o[i] - c[i - 1]) > 1.5 * (atr[i - 1] if not np.isnan(atr[i - 1]) else 0) or roll[i])
        sigL = (not blocked) and sL != "" and not (dL > cfg.max_stop * a)
        sigSraw = (not blocked) and sS != "" and not (dS > cfg.max_stop * a) and not sigL
        sigS = sigSraw and cfg.short_ok
        sigX = sigSraw and not cfg.short_ok

        # lifecycle
        if st["state"] == 1:
            d = st["dir"]
            if (l[i] <= st["lim"]) if d == 1 else (h[i] >= st["lim"]):
                st["fill"] = min(o[i], st["lim"]) if d == 1 else max(o[i], st["lim"])
                st["fillbar"], st["state"] = i, 2
            elif i - st["bar"] >= cfg.expiry:
                st["state"] = 3
        if st["state"] == 2:
            d = st["dir"]
            hitStop = l[i] <= st["cur"] if d == 1 else h[i] >= st["cur"]
            hitT2 = h[i] >= st["t2"] if d == 1 else l[i] <= st["t2"]
            hitT1 = h[i] >= st["t1"] if d == 1 else l[i] <= st["t1"]
            if hitStop:
                gap = i != st["fillbar"]
                px = (min(o[i], st["cur"]) if d == 1 else max(o[i], st["cur"])) if gap else st["cur"]
                close_trade(px, "BE" if st["t1hit"] else "SL", i)
            else:
                if hitT1 and not st["t1hit"]:
                    st["t1hit"], st["cur"] = True, st["fill"]
                if hitT2:
                    close_trade(st["t2"], "T2", i)
                elif i - st["fillbar"] >= cfg.max_hold:
                    close_trade(c[i], "TIME", i)
                elif cfg.reg_exit and tr == -d:
                    close_trade(c[i], "INVALID", i)
        if sigL or sigS or sigX:
            d = 1 if sigL else -1
            if st["state"] == 2 and st["dir"] == -d:
                close_trade(c[i], "OPP", i)
            elif st["state"] == 1 and st["dir"] == -d:
                st["state"] = 3
            busy = st["state"] in (1, 2) and st["dir"] == d
            if (sigL or sigS) and not busy:
                stop = stopL if d == 1 else stopS
                rp = abs(c[i] - stop)
                st.update(dir=d, state=1, ref=c[i], lim=c[i] + d * cfg.chase * a, stop=stop, cur=stop,
                          t1=c[i] + d * cfg.t1R * rp, t2=c[i] + d * cfg.t2R * rp, fill=np.nan,
                          bar=i, fillbar=-1, t1hit=False, strat=sL if d == 1 else sS)
    return pd.DataFrame(trades), dict(in_trade=in_trade, regime=regime, n=n)


# ───────────────────────── Metrics ─────────────────────────

def metrics(tr: pd.DataFrame, bars: int, in_trade_bars: int, cfg: Cfg, risk=0.01) -> dict:
    if tr is None or len(tr) == 0:
        return dict(trades=0, exposure=round(100 * in_trade_bars / max(bars, 1), 1))
    R = tr["R_net"].to_numpy()
    wins, losses = R[R > 0], R[R <= 0]
    # equity: fixed-fractional risk, capped by leverage (risk_frac_px = stop distance / price)
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r, rf in zip(R, tr["risk_frac_px"].to_numpy()):
        f = min(risk, cfg.leverage * rf)
        eq *= 1 + r * f
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak)
    streak = mx = 0
    for r in R:
        streak = streak + 1 if r <= 0 else 0
        mx = max(mx, streak)
    return dict(
        trades=len(R),
        win_rate=round(100 * len(wins) / len(R), 1),
        avg_win_R=round(wins.mean(), 2) if len(wins) else 0.0,
        avg_loss_R=round(losses.mean(), 2) if len(losses) else 0.0,
        expectancy_R=round(R.mean(), 3),
        pf=round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else float("inf"),
        total_R=round(R.sum(), 1),
        ret_pct=round(100 * (eq - 1), 1),
        max_dd_pct=round(100 * mdd, 1),
        max_loss_streak=mx,
        exposure=round(100 * in_trade_bars / max(bars, 1), 1),
    )
