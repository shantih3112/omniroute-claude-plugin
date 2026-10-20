"""The paper signal service.

One cycle (`step`) per poll interval:
  1. pull completed M1 bars per symbol; gate each through the live data-quality check;
  2. advance paper tracking of every active signal with those bars (lifecycle events → updates);
  3. build M15/H1 bars incrementally; on each completed H1 bar run the configured strategies;
  4. pass every candidate through the explicit no-trade policy and the independent risk engine;
  5. store approved signals immutably, enqueue the message, count abstain reasons otherwise;
  6. write a heartbeat; once a day enqueue the daily report (also on days without signals).

Routing: `research` strategies → admin chat only. Only `paper_forward` or better may reach the
broadcast channel (docs/SCORECARD.md). Live order execution does not exist in this codebase.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .. import features as F
from .. import instruments
from ..backtest.engine import BASE, _commission_price, _spread
from ..data.quality import check_live_bar
from ..data.resample import resample
from ..news import calendar as cal
from ..risk.engine import OpenRisk, PortfolioState, Proposal, RiskConfig, RiskEngine, currency_exposure
from ..signals.lifecycle import Bar, PaperTracker
from ..signals.store import SignalRecord, Store
from ..strategies.library import REGISTRY
from ..telegram import format as fmt
from ..timeutil import OSLO, fx_day, is_illiquid_holiday, iso, market_open
from .aggregate import Aggregator

ROUTE = {"research": "admin", "paper_forward": "broadcast", "holdout_confirmed": "broadcast"}
STRAT_CODE = {"trend_pullback": "TP", "tsmom_weekly": "TS", "donchian_d1": "DC", "ma_cross": "MA",
              "squeeze_breakout": "SQ", "sweep_reversal": "SW", "bb_reversion": "BB", "asian_breakout": "AB",
              "usd_fix": "UF", "round_break": "RN", "random": "RD"}


@dataclass
class SymState:
    symbol: str
    h1: Aggregator = field(default_factory=lambda: Aggregator(60, max_keep=20000))
    last_bar_t: pd.Timestamp | None = None
    last_bar_wall: pd.Timestamp | None = None
    closes: deque = field(default_factory=lambda: deque(maxlen=240))
    status: str = "starting"
    status_reason: str = ""
    last_spread_pips: float | None = None


class Service:
    def __init__(self, cfg: dict, store: Store, feed, label: str = "REPLAY", base_dir: Path | None = None):
        self.cfg, self.store, self.feed, self.label = cfg, store, feed, label
        self.base_dir = base_dir or Path.cwd()
        self.symbols = list(cfg["symbols"])
        self.risk = RiskEngine(RiskConfig(**cfg.get("risk", {})), self.base_dir)
        self.trackers = {s: PaperTracker(instruments.get(s), BASE, paper_delay_min=1) for s in self.symbols}
        self.st = {s: SymState(s) for s in self.symbols}
        self.strats = [(c["family"], c.get("params", {}), c.get("status", "research")) for c in cfg.get("strategies", [])]
        self.news_cfg = cfg.get("news", {})
        self.calendar: list[cal.CalEvent] = []
        self.calendar_fetched: pd.Timestamp | None = None
        self.corr: dict[tuple[str, str], float] = {}

    # ------------------------------------------------------------------ bootstrap / restore
    def seed_history(self, symbol: str, h1: pd.DataFrame) -> None:
        self.st[symbol].h1.seed(h1.tail(20000))

    def restore(self) -> dict:
        """After a restart: reload calendar/state from the DB; active signals keep tracking."""
        now = self.feed.now()
        a, b = cal.window(now, 48, 24 * 8)
        self.calendar = cal.rows_to_events(self.store.calendar_between(a, b))
        lf = self.store.kv_get("calendar_fetched_at")
        self.calendar_fetched = pd.Timestamp(lf) if lf else None
        act = self.store.active_signals()
        resumed = {}
        for sym in self.symbols:
            row = self.store.conn.execute("SELECT MAX(t) m FROM bars WHERE symbol=? AND tf='M1'", (sym,)).fetchone()
            if row and row["m"]:
                last = pd.Timestamp(row["m"])
                self.st[sym].last_bar_t = last
                if hasattr(self.feed, "last"):
                    # catch up from the last bar we processed, so tracking never skips minutes
                    self.feed.last[sym] = last
                resumed[sym] = iso(last)
        self.store.incident(iso(now), "restart", f"restored {len(act)} active signals, mode={self.label}, "
                                                 f"resume from {resumed}")
        return {"active_signals": len(act), "calendar_events": len(self.calendar), "resume_from": resumed}

    def prune(self, keep_days: int = 30) -> None:
        self.store.prune_bars(iso(pd.Timestamp(self.feed.now()) - pd.Timedelta(days=keep_days)))

    def set_calendar(self, events: list[cal.CalEvent], fetched_at: pd.Timestamp) -> dict:
        counts = {"new": 0, "revised": 0, "same": 0}
        for e in events:
            counts[self.store.upsert_calendar(e.__dict__, iso(fetched_at))] += 1
        self.calendar_fetched = fetched_at
        self.store.kv_set("calendar_fetched_at", iso(fetched_at), iso(fetched_at))
        a, b = cal.window(fetched_at, 48, 24 * 8)
        self.calendar = cal.rows_to_events(self.store.calendar_between(a, b))
        return counts

    def update_correlations(self) -> None:
        """60-day correlation of daily returns between symbols (causal: completed D1 bars only)."""
        rets = {}
        for s in self.symbols:
            h1 = self.st[s].h1.frame()
            if len(h1) > 24 * 70:
                d = resample(h1, "D1")["close"]
                rets[s] = np.log(d).diff().tail(60)
        if len(rets) < 2:
            return
        df = pd.DataFrame(rets).dropna()
        c = df.corr()
        self.corr = {(a, b): float(c.loc[a, b]) for a in c.index for b in c.columns if a != b}

    # ------------------------------------------------------------------ main cycle
    async def step(self) -> dict:
        now = pd.Timestamp(self.feed.now())
        stats = {"bars": 0, "signals": 0, "events": 0, "rejected": 0}
        for sym in self.symbols:
            ss = self.st[sym]
            try:
                batch = await self.feed.poll(sym)
            except Exception as ex:  # feed failure pauses this symbol only
                if ss.status != "feed_error":
                    self.store.incident(iso(now), "feed_error", f"{sym}: {type(ex).__name__}: {str(ex)[:200]}")
                ss.status, ss.status_reason = "feed_error", f"{type(ex).__name__}"
                continue
            for bar in batch.bars:
                # per-bar staleness is not checked here: catch-up bars after an outage are valid
                # history; freshness of the feed as a whole is judged in _update_data_status
                v = check_live_bar(bar.t, ss.last_bar_t, now, bar.o, bar.h, bar.l, bar.c, 1,
                                   max_staleness_min=1e9,
                                   recent_closes=np.array(ss.closes) if len(ss.closes) > 30 else None)
                if not v.ok and any("out-of-order" in r or "inconsistent" in r for r in v.reasons):
                    self.store.incident(iso(now), "bad_bar", f"{sym} {bar.t}: {'; '.join(v.reasons)}")
                    continue
                if not v.ok and any("jump" in r for r in v.reasons):
                    ss.status, ss.status_reason = "suspect", v.reasons[0]
                stats["bars"] += 1
                ss.last_bar_t, ss.last_bar_wall = bar.t, now
                ss.closes.append(bar.c)
                if bar.spread is not None:
                    ss.last_spread_pips = bar.spread / instruments.get(sym).pip_size
                self.store.upsert_bars(sym, "M1", [(iso(bar.t), bar.o, bar.h, bar.l, bar.c, None, bar.spread)])
                stats["events"] += self._track(sym, bar)
                for built in ss.h1.add(bar):
                    stats["signals"] += self._on_h1_close(sym, built, now, stats)
            for built in ss.h1.tick(now):
                stats["signals"] += self._on_h1_close(sym, built, now, stats)
            self._update_data_status(sym, now)
        self._maybe_daily_report(now)
        self._heartbeat(now, stats)
        return stats

    def _update_data_status(self, sym: str, now: pd.Timestamp) -> None:
        ss = self.st[sym]
        if ss.status == "feed_error" and ss.last_bar_wall is not None and ss.last_bar_wall >= now - pd.Timedelta(minutes=1):
            ss.status = "ok"
        if not market_open(now.to_pydatetime()):
            ss.status, ss.status_reason = "market_closed", ""
            return
        if ss.last_bar_t is None:
            ss.status, ss.status_reason = "no_data", "no bars received yet"
            return
        age = (now - (ss.last_bar_t + pd.Timedelta(minutes=1))).total_seconds()
        if age > self.risk.cfg.max_data_age_s:
            if ss.status != "stale":
                self.store.incident(iso(now), "stale_data", f"{sym}: last bar {age:.0f}s old")
            ss.status, ss.status_reason = "stale", f"last bar {age:.0f}s old"
        elif ss.status in ("starting", "stale", "no_data", "market_closed"):
            ss.status, ss.status_reason = "ok", ""

    # ------------------------------------------------------------------ lifecycle tracking
    def _track(self, sym: str, bar: Bar) -> int:
        n = 0
        inst = instruments.get(sym)
        for sig in [s for s in self.store.active_signals() if s["symbol"] == sym]:
            key = f"track:{sig['id']}"
            st = self.store.kv_get(key, {"phase": "pending", "published_at": sig["created_at"]})
            st, trs = self.trackers[sym].step(sig, st, bar)
            self.store.kv_set(key, st, iso(bar.t))
            for tr in trs:
                self.store.add_event(sig["id"], iso(tr.ts), tr.kind, tr.price, tr.r_result, tr.detail)
                text = fmt.update(sig, inst, tr.kind, tr.ts, tr.price, tr.r_result, tr.detail)
                self.store.enqueue(f"evt:{sig['id']}:{tr.kind}", ROUTE[sig["evidence_class"]], "update",
                                   self._tag(text), iso(tr.ts))
                n += 1
        return n

    # ------------------------------------------------------------------ signal generation
    def _on_h1_close(self, sym: str, built, now: pd.Timestamp, stats: dict) -> int:
        close_t = built.t + pd.Timedelta(hours=1)
        h1 = self.st[sym].h1.frame()
        h1.attrs["symbol"] = sym
        if len(h1) < 600:
            return 0
        created = 0
        for fam, params, status in self.strats:
            strat = REGISTRY[fam](**params)
            sig = strat.generate(h1)
            sig = sig[sig["time"] == close_t]
            for row in sig.itertuples(index=False):
                ok, reasons, rec = self._policy(sym, fam, strat, status, row, now)
                if ok:
                    if self._publish(rec, sym, now, row):
                        created += 1
                else:
                    stats["rejected"] += 1
                    self._abstain(now, reasons, sym, fam, close_t)
        return created

    def _policy(self, sym, fam, strat, status, row, now):
        """Explicit no-trade policy. Returns (ok, reasons, SignalRecord|None)."""
        inst = instruments.get(sym)
        ss = self.st[sym]
        reasons = []
        if self.label != "REPLAY" and (now - pd.Timestamp(row.time)) > pd.Timedelta(minutes=5):
            reasons.append("signal bar closed more than 5 min ago (processing lag)")
        if ss.status not in ("ok",):
            reasons.append(f"data not OK: {ss.status} {ss.status_reason}".strip())
        if not market_open(pd.Timestamp(row.time).to_pydatetime()):
            reasons.append("market closed")
        if is_illiquid_holiday(pd.Timestamp(row.time).to_pydatetime()):
            reasons.append("holiday liquidity")
        bo = cal.blackout(inst.currencies, now, self.calendar, self.calendar_fetched,
                          self.news_cfg.get("blackout_before_min", 30), self.news_cfg.get("blackout_after_min", 30),
                          impacts=tuple(self.news_cfg.get("impact_levels", ["High"])),
                          max_age_h=self.news_cfg.get("max_calendar_age_h", 26),
                          fail_closed=self.news_cfg.get("fail_closed", True))
        reasons += bo.reasons
        side = int(row.side)
        hour = pd.Timestamp(row.time).hour
        spread = _spread(inst, hour, BASE)
        if ss.last_spread_pips is not None:
            spread = max(spread, ss.last_spread_pips * inst.pip_size)
        risk_dist = abs(row.entry_ref - row.stop) + (spread if side == 1 else 0)
        cost = spread + _commission_price(inst, BASE)
        cost_r = cost / risk_dist if risk_dist > 0 else 9.9
        tgt = None if pd.isna(row.target) else float(row.target)
        st = self.portfolio_state(now)
        prop = Proposal("?", sym, side, float(row.entry_ref), float(row.stop), tgt,
                        spread / inst.pip_size, 0.0 if self.label == "REPLAY" else
                        (now - (ss.last_bar_t + pd.Timedelta(minutes=1))).total_seconds() if ss.last_bar_t is not None else 1e9,
                        cost_r)
        dec = self.risk.evaluate(prop, inst, st, self.corr)
        reasons += dec.reasons
        if reasons:
            return False, reasons, None
        zone = (row.entry_ref - 0.5 * risk_dist, row.entry_ref + 0.25 * risk_dist) if side == 1 else \
               (row.entry_ref - 0.25 * risk_dist, row.entry_ref + 0.5 * risk_dist)
        t = pd.Timestamp(row.time)
        sid = f"{t.strftime('%y%m%d-%H%M')}-{sym}-{STRAT_CODE.get(fam, fam[:2].upper())}"
        rr = None if tgt is None else (abs(tgt - row.entry_ref) - cost) / risk_dist
        hold_end = t + pd.Timedelta(minutes=float(row.max_hold_min))
        during = cal.events_during(inst.currencies, t, hold_end, self.calendar)
        ex = currency_exposure(st.open)
        ctx = {
            "regime": row.regime or "",
            "news": ("CALENDAR UNAVAILABLE - news risk unknown" if self.calendar_fetched is None else
                     "; ".join(f"{e.currency} {e.title} {pd.Timestamp(e.scheduled_at).tz_convert(OSLO).strftime('%a %H:%M')}"
                               for e in during[:4]) or "no high-impact events scheduled in the holding window "
                                                        "(unscheduled news is not covered)"),
            "exposure": ", ".join(f"{k} {v:+.1f}%" for k, v in ex.items() if abs(v) > 0) or "no other open paper signals",
            "htf": self._htf_note(sym),
            "warnings": dec.warnings,
            "mode": self.label,
        }
        rec = SignalRecord(
            id=sid, created_at=iso(t), symbol=sym, side=side, strategy=fam, strategy_version=strat.version,
            evidence_class=status, entry_type=row.entry_type, entry_ref=float(row.entry_ref),
            zone_lo=float(zone[0]), zone_hi=float(zone[1]), stop=float(row.stop), target=tgt,
            max_hold_min=float(row.max_hold_min), expires_at=iso(t + pd.Timedelta(minutes=float(row.expiry_min))),
            risk_pct=dec.risk_pct, est_cost_r=round(cost_r, 3), rr_after_costs=None if rr is None else round(rr, 2),
            context=ctx, rationale=str(row.note))
        return True, [], rec

    def _htf_note(self, sym: str) -> str:
        h1 = self.st[sym].h1.frame()
        if len(h1) < 24 * 60:
            return ""
        d = resample(h1, "D1")
        e50 = F.ema(d["close"], 50)
        if pd.isna(e50.iloc[-2]):
            return ""
        c = d["close"].iloc[-2]  # last COMPLETED day (the newest may be in progress)
        return f"D1 close {'above' if c > e50.iloc[-2] else 'below'} EMA50"

    def _publish(self, rec: SignalRecord, sym: str, now: pd.Timestamp, row) -> bool:
        if not self.store.add_signal(rec, iso(now)):
            return False  # already exists (restart re-evaluated the same bar): no duplicate
        sig = self.store.signal(rec.id)
        self.store.add_event(rec.id, iso(now), "published", detail={"channel": ROUTE[rec.evidence_class]})
        text = fmt.new_signal(sig, instruments.get(sym), dict(rec.context, published_at=iso(now)))
        self.store.enqueue(f"new:{rec.id}", ROUTE[rec.evidence_class], "signal", self._tag(text), iso(now))
        return True

    def _tag(self, text: str) -> str:
        return (f"<b>[{self.label}]</b> " + text) if self.label != "LIVE" else text

    def _abstain(self, now, reasons, sym, fam, t):
        day = str(fx_day(now).date())
        key = f"abstain:{day}"
        d = self.store.kv_get(key, {})
        for r in reasons:
            k = r.split(":")[0].split("(")[0].strip()[:60]
            d[k] = d.get(k, 0) + 1
        self.store.kv_set(key, d, iso(now))

    def latest_prices(self) -> dict[str, float]:
        return {s: float(v.closes[-1]) for s, v in self.st.items() if v.closes}

    # ------------------------------------------------------------------ paper portfolio
    def portfolio_state(self, now: pd.Timestamp) -> PortfolioState:
        closed = self.store.closed_results()
        sig_risk = {s["id"]: s["risk_pct"] for s in self.store.conn.execute("SELECT id, risk_pct FROM signals")}
        eq = 100.0
        peak = 100.0
        day0 = fx_day(now)
        day_start = 100.0
        streak = 0
        for c in closed:
            pnl = (c["r_result"] or 0.0) * sig_risk.get(c["id"], 0.5)
            if fx_day(pd.Timestamp(c["ts"])) < day0:
                day_start += pnl
            eq += pnl
            peak = max(peak, eq)
            streak = streak + 1 if (c["r_result"] or 0) < 0 else 0
        open_ = []
        for s in self.store.active_signals():
            inst = instruments.get(s["symbol"])
            open_.append(OpenRisk(s["id"], s["symbol"], s["side"], s["risk_pct"], inst.base, inst.quote))
        paused = bool(self.store.kv_get("paused", False))
        return PortfolioState(equity_pct=eq, peak_equity_pct=peak, day_start_equity_pct=day_start, open=open_,
                              consecutive_losses=streak, paused=paused,
                              pause_reason=self.store.kv_get("pause_reason", ""))

    # ------------------------------------------------------------------ reports / health
    def _maybe_daily_report(self, now: pd.Timestamp) -> None:
        oslo = now.tz_convert(OSLO)
        if oslo.hour < 22 or (oslo.hour == 22 and oslo.minute < 30):
            return
        day = str(oslo.date())
        if self.store.kv_get("last_daily") == day:
            return
        self.store.enqueue(f"daily:{day}", "admin", "report", self._tag(fmt.daily_report(day, self.daily_stats(now))),
                           iso(now))
        if any(st == "paper_forward" or st == "holdout_confirmed" for _, _, st in self.strats):
            self.store.enqueue(f"daily-bc:{day}", "broadcast", "report",
                               self._tag(fmt.daily_report(day, self.daily_stats(now, public=True))), iso(now))
        self.store.kv_set("last_daily", day, iso(now))

    def daily_stats(self, now: pd.Timestamp, public: bool = False) -> dict:
        a = iso(now - pd.Timedelta(hours=24))
        sigs = self.store.signals_between(a, iso(now))
        closed = [c for c in self.store.closed_results() if c["ts"] >= a]
        ab = self.store.kv_get(f"abstain:{fx_day(now).date()}", {})
        ob = self.store.outbox_stats()
        data = ", ".join(f"{s}:{self.st[s].status}" for s in self.symbols)
        fresh = self.calendar_fetched is not None and now - self.calendar_fetched < pd.Timedelta(
            hours=self.news_cfg.get("max_calendar_age_h", 26))
        if fresh:
            cal_status = f"fresh (fetched {iso(self.calendar_fetched)})"
        elif self.news_cfg.get("fail_closed", True):
            cal_status = "UNAVAILABLE - new signals blocked (fail-closed)"
        else:
            cal_status = "UNAVAILABLE - fail-open configured: news risk NOT checked"
        strategies_live = [s for _, _, s in self.strats]
        note = ("No strategy has passed the validation gates; everything here is research output."
                if all(s == "research" for s in strategies_live) else
                "Paper results only. Past and paper results do not predict future results.")
        return {"new_signals": len(sigs), "abstain_reasons": ab, "closed": len(closed),
                "closed_r": sum((c["r_result"] or 0) for c in closed), "open": len(self.store.active_signals()),
                "data_status": data, "calendar_status": cal_status,
                "delivery_status": f"accepted by Telegram API: {ob.get('accepted', 0)}, pending: {ob.get('pending', 0)}, "
                                   f"failed: {ob.get('failed', 0)} (acceptance is not proof of receipt)",
                "evidence_note": note}

    def health(self, now: pd.Timestamp | None = None) -> dict:
        now = pd.Timestamp(now or self.feed.now())
        ob = self.store.outbox_stats()
        return {"ts": iso(now), "mode": self.label,
                "symbols": {s: {"status": v.status, "reason": v.status_reason,
                                "last_bar": iso(v.last_bar_t) if v.last_bar_t is not None else None}
                            for s, v in self.st.items()},
                "calendar_fetched": iso(self.calendar_fetched) if self.calendar_fetched is not None else None,
                "paused": bool(self.store.kv_get("paused", False)), "kill_switch": self.risk.kill_switch_on(),
                "active_signals": len(self.store.active_signals()), "outbox": ob}

    def _heartbeat(self, now: pd.Timestamp, stats: dict) -> None:
        hb = self.cfg.get("ops", {}).get("heartbeat_file")
        if not hb:
            return
        p = Path(hb) if Path(hb).is_absolute() else self.base_dir / hb
        p.parent.mkdir(parents=True, exist_ok=True)
        body = dict(self.health(now), wall_clock=iso(pd.Timestamp.now(tz="UTC")), last_cycle=stats)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, default=str))
        tmp.replace(p)  # atomic
