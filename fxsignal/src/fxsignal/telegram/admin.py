"""Admin bot commands.

Only Telegram user IDs listed in TELEGRAM_ADMIN_IDS may run commands; everyone else gets no
reply at all (no information leak, no error oracle). Commands never alter execution
permissions (there is no execution), never edit or delete signals, and /pause only stops NEW
signals: tracking and updates of existing signals continue, and the reply says so.

/size is a private calculator: it uses only the numbers the requester types and is answered in
the private chat, never in the channel.
"""
from __future__ import annotations

import shlex

import pandas as pd

from .. import instruments
from ..risk.engine import currency_exposure
from ..risk.sizing import size_position
from ..timeutil import fmt_oslo, iso
from . import format as fmt

HELP = """<b>Commands</b> (admin only)
/status – service, data, calendar and delivery health
/signals – open and pending signals
/performance – paper results by evidence class
/risk – paper exposure and risk limits
/news – high-impact events in the next 24 h
/pause [reason] – stop NEW signals (existing ones keep being tracked)
/resume – allow new signals again
/kill on|off – kill switch (blocks all new signals until turned off)
/size SYMBOL EQUITY CCY RISK% ENTRY STOP – private position-size calculator
/help – this text"""


class Admin:
    def __init__(self, service, admin_ids: set[int]):
        self.svc = service
        self.admins = admin_ids

    def authorized(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admins

    def handle(self, user_id: int | None, text: str) -> str | None:
        if not self.authorized(user_id):
            return None
        try:
            parts = shlex.split(text.strip())
        except ValueError:
            return "Could not parse the command."
        if not parts or not parts[0].startswith("/"):
            return None
        cmd = parts[0].split("@")[0].lower()
        args = parts[1:]
        fn = getattr(self, "cmd_" + cmd[1:], None)
        if fn is None:
            return "Unknown command. /help"
        return fn(args)

    # ------------------------------------------------------------------------------------
    def cmd_help(self, args):
        return HELP

    def cmd_start(self, args):
        return HELP

    def cmd_status(self, args):
        h = self.svc.health()
        lines = [f"<b>Status</b> ({fmt.e(h['mode'])}) {fmt.e(fmt_oslo(pd.Timestamp(h['ts'])))}",
                 f"New signals: {'PAUSED' if h['paused'] else 'allowed'} · kill switch: {'ON' if h['kill_switch'] else 'off'}",
                 f"Active signals: {h['active_signals']}",
                 f"Calendar fetched: {fmt.e(fmt_oslo(pd.Timestamp(h['calendar_fetched'])) if h['calendar_fetched'] else 'never')}",
                 f"Outbox: {fmt.e(h['outbox'])}", "<b>Data</b>"]
        for s, v in h["symbols"].items():
            lines.append(f"{s}: {fmt.e(v['status'])} {fmt.e(v['reason'])}")
        lines.append("Execution: not implemented (signal-only).")
        return "\n".join(lines)

    def cmd_signals(self, args):
        act = self.svc.store.active_signals()
        if not act:
            return "No open or pending signals."
        out = ["<b>Open / pending</b>"]
        for s in act:
            inst = instruments.get(s["symbol"])
            out.append(f"{fmt.e(s['id'])} {fmt.SIDE[s['side']]} {s['symbol']} · {s['state']} · stop {fmt.px(inst, s['stop'])}"
                       f" · target {fmt.px(inst, s['target'])} · {s['evidence_class']}")
        return "\n".join(out)

    def cmd_performance(self, args):
        out = ["<b>Paper performance</b> (modelled fills; hypothetical)"]
        for cls in ("research", "paper_forward", "holdout_confirmed"):
            rows = self.svc.store.closed_results(cls)
            if not rows:
                continue
            r = [x["r_result"] or 0.0 for x in rows]
            wins = sum(1 for x in r if x > 0)
            out.append(f"{cls}: {len(r)} closed · {sum(r):+.2f} R · avg {sum(r) / len(r):+.3f} R · wins {wins}/{len(r)}")
        if len(out) == 1:
            out.append("No closed signals yet.")
        out.append("Small samples say little; see docs/SCORECARD.md for the forward-test minimums.")
        return "\n".join(out)

    def cmd_risk(self, args):
        st = self.svc.portfolio_state(pd.Timestamp(self.svc.feed.now()))
        c = self.svc.risk.cfg
        ex = currency_exposure(st.open)
        return "\n".join([
            "<b>Paper portfolio risk</b> (system signals only — not your account)",
            f"Open risk: {sum(o.risk_pct for o in st.open):.2f}% / limit {c.max_open_risk_pct}%",
            "Currency exposure: " + (", ".join(f"{k} {v:+.2f}%" for k, v in ex.items() if abs(v) > 1e-9) or "none"),
            f"Paper equity: {st.equity_pct:.2f}% of start · peak {st.peak_equity_pct:.2f}%",
            f"Consecutive losses: {st.consecutive_losses} (risk halves at {c.losing_streak_reduce}, pause at {c.losing_streak_pause})",
            f"Per-trade risk {c.risk_per_trade_pct}% (hard cap {c.hard_max_risk_per_trade_pct}%), daily stop {c.daily_loss_stop_pct}%, "
            f"drawdown stop {c.overall_drawdown_stop_pct}%"])

    def cmd_news(self, args):
        now = pd.Timestamp(self.svc.feed.now())
        ev = [e for e in self.svc.calendar if e.impact == "High" and now <= pd.Timestamp(e.scheduled_at) <= now + pd.Timedelta(hours=24)]
        if self.svc.calendar_fetched is None:
            return "Calendar not available: new signals are blocked (fail-closed)."
        if not ev:
            return "No high-impact events in the next 24 h (per the calendar source; unscheduled news is not covered)."
        return "<b>High-impact, next 24 h</b>\n" + "\n".join(
            f"{fmt.e(fmt_oslo(pd.Timestamp(e.scheduled_at)))} {e.currency} {fmt.e(e.title)}" for e in ev[:20])

    def cmd_pause(self, args):
        now = iso(pd.Timestamp(self.svc.feed.now()))
        reason = " ".join(args) or "admin pause"
        self.svc.store.kv_set("paused", True, now)
        self.svc.store.kv_set("pause_reason", reason, now)
        self.svc.store.incident(now, "paused", reason)
        n = len(self.svc.store.active_signals())
        return (f"New signals paused ({fmt.e(reason)}). {n} existing signal(s) are still tracked and will receive "
                "updates. Nothing else changed.")

    def cmd_resume(self, args):
        now = iso(pd.Timestamp(self.svc.feed.now()))
        self.svc.store.kv_set("paused", False, now)
        self.svc.store.incident(now, "resumed", "")
        return "New signals allowed again. Risk limits and data checks still apply."

    def cmd_kill(self, args):
        p = self.svc.base_dir / self.svc.risk.cfg.kill_switch_file
        now = iso(pd.Timestamp(self.svc.feed.now()))
        if args and args[0].lower() == "on":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(now)
            self.svc.store.incident(now, "kill_switch", "on")
            return "Kill switch ON: no new signals. Existing signals are still tracked."
        if args and args[0].lower() == "off":
            if p.exists():
                p.unlink()
            self.svc.store.incident(now, "kill_switch", "off")
            return "Kill switch off."
        return f"Kill switch is {'ON' if self.svc.risk.kill_switch_on() else 'off'}. Use /kill on|off."

    def cmd_size(self, args):
        if len(args) != 6:
            return "Usage: /size EURUSD 10000 USD 0.5 1.0850 1.0820"
        sym, equity, ccy, risk, entry, stop = args
        try:
            inst = instruments.get(sym)
            equity, risk, entry, stop = float(equity), float(risk), float(entry), float(stop)
        except (KeyError, ValueError) as ex:
            return f"Invalid input: {fmt.e(ex)}"
        if risk > self.svc.risk.cfg.hard_max_risk_per_trade_pct:
            return f"Refused: {risk}% exceeds the hard cap of {self.svc.risk.cfg.hard_max_risk_per_trade_pct}% per trade."
        prices = self.svc.latest_prices() if hasattr(self.svc, "latest_prices") else {}
        prices.setdefault(sym.upper(), entry)
        r = size_position(inst, equity, ccy.upper(), risk, entry, stop, prices,
                          spread_price=inst.spread_pips * inst.pip_size)
        if not r.ok:
            return f"No trade: {fmt.e(r.reason)}"
        return (f"<b>{sym.upper()}</b> {r.lots:.2f} lots risks about {r.risk_amount:.2f} {ccy.upper()} "
                f"({r.risk_pct:.2f}%) at the stop incl. typical spread and commission. Margin ≈ {r.margin:.2f} {ccy.upper()}. "
                f"{fmt.e(r.gap_note)} Uses the numbers you typed and the latest known FX rates; check your broker's "
                "contract specs.")
