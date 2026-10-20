"""Telegram message rendering (HTML parse mode).

Style rules: plain language, no hype, no emojis beyond a single status marker, no invented
certainty, no return promises. Every trade message states its evidence class. Times are shown
in Europe/Oslo with the zone abbreviation. Personal account details never appear in channel
messages; sizes are illustrative percentages, and /size gives a private calculation.
"""
from __future__ import annotations

import html

import pandas as pd

from ..instruments import Instrument
from ..timeutil import fmt_oslo

MAX_LEN = 4000  # Telegram limit is 4096 characters; keep a margin

EVIDENCE_LABEL = {
    "research": "RESEARCH ONLY - no validated edge. Do not trade this.",
    "paper_forward": "PAPER - passed historical gates, forward test in progress. Not a recommendation.",
    "holdout_confirmed": "PAPER - passed historical and holdout tests; forward evidence still limited.",
}
SIDE = {1: "BUY", -1: "SELL"}


def e(x) -> str:
    return html.escape(str(x), quote=False)


def px(inst: Instrument, v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    return f"{float(v):.{inst.digits}f}"


def pips(inst: Instrument, a: float, b: float) -> str:
    return f"{abs(a - b) / inst.pip_size:.1f}"


def new_signal(sig: dict, inst: Instrument, ctx: dict) -> str:
    """Render the canonical NEW SIGNAL message from the stored (immutable) signal row."""
    side = int(sig["side"])
    lines = [
        f"<b>{e(sig['id'])} | {e(sig['symbol'])} | {SIDE[side]}</b>",
        f"<i>{e(EVIDENCE_LABEL[sig['evidence_class']])}</i>",
        "",
        "<b>Status:</b> Pending",
        f"<b>Created:</b> {e(fmt_oslo(pd.Timestamp(sig['created_at'])))}",
        f"<b>Published:</b> {e(fmt_oslo(pd.Timestamp(ctx.get('published_at', sig['created_at']))))}",
        f"<b>Expires:</b> {e(fmt_oslo(pd.Timestamp(sig['expires_at'])))}",
        "",
        "<b>Plan</b>",
        f"Entry: market, only inside {px(inst, sig['zone_lo'])} – {px(inst, sig['zone_hi'])}",
        f"Stop: {px(inst, sig['stop'])} ({pips(inst, sig['entry_ref'], sig['stop'])} pips)",
        f"Target: {px(inst, sig['target'])}" + (f" ({pips(inst, sig['entry_ref'], sig['target'])} pips)"
                                                 if sig.get('target') is not None else " (none - time/trailing exit)"),
        f"Time stop: {int(sig['max_hold_min'] // 60)} h after entry",
        "Outside the zone or after expiry: <b>do not chase</b>.",
        "",
        "<b>Risk</b>",
        f"Illustrative risk: {sig['risk_pct']:.2f}% of account. Size from YOUR account with /size.",
        f"Est. costs: {sig['est_cost_r']:.2f} R"
        + (f" · reward:risk after costs {sig['rr_after_costs']:.2f}" if sig.get("rr_after_costs") else ""),
        "Stops can fill worse in gaps and fast markets.",
        "",
        "<b>Context</b>",
        f"Strategy: {e(sig['strategy'])} v{e(sig['strategy_version'])}",
    ]
    for k in ("htf", "regime", "news", "exposure"):
        if ctx.get(k):
            lines.append(f"{k.upper() if k == 'htf' else k.capitalize()}: {e(ctx[k])}")
    lines += [f"Why: {e(sig['rationale'])}",
              f"Cancel if: {e(ctx.get('cancel_if', 'the stop trades before entry, or the entry zone is left'))}"]
    return _cap("\n".join(lines))


def update(sig: dict, inst: Instrument, kind: str, ts, price=None, r=None, detail: dict | None = None) -> str:
    detail = detail or {}
    title = {"triggered": "Triggered", "missed": "Do not chase", "expired": "Expired", "cancelled": "Cancelled",
             "closed": "Closed", "note": "Update"}.get(kind, kind)
    lines = [f"<b>{e(sig['id'])} | {e(sig['symbol'])} | {SIDE[int(sig['side'])]} — {title}</b>",
             f"{e(fmt_oslo(pd.Timestamp(ts)))}"]
    if price is not None:
        lines.append(f"Paper price: {px(inst, price)}")
    if kind == "closed" and r is not None:
        lines.append(f"Result: {r:+.2f} R after modelled costs ({e(detail.get('reason', ''))})")
    if detail.get("why"):
        lines.append(e(detail["why"]))
    lines.append("<i>Paper tracking with modelled prices; your fills will differ.</i>")
    return _cap("\n".join(lines))


def daily_report(day: str, stats: dict) -> str:
    lines = [f"<b>Daily report — {e(day)}</b>", ""]
    n = stats.get("new_signals", 0)
    lines.append(f"New signals: {n}")
    if n == 0:
        lines.append("No qualified signals today.")
    if stats.get("abstain_reasons"):
        lines.append("Why the system abstained:")
        for k, v in sorted(stats["abstain_reasons"].items(), key=lambda x: -x[1])[:8]:
            lines.append(f"• {e(k)}: {v}")
    if stats.get("closed"):
        lines.append(f"Closed today: {stats['closed']} · total {stats.get('closed_r', 0):+.2f} R (paper)")
    if stats.get("open"):
        lines.append(f"Open/pending signals: {stats['open']}")
    lines += ["", f"Data: {e(stats.get('data_status', 'unknown'))}",
              f"Calendar: {e(stats.get('calendar_status', 'unknown'))}",
              f"Delivery: {e(stats.get('delivery_status', 'unknown'))}",
              "", f"<i>{e(stats.get('evidence_note', 'No strategy has passed the validation gates; output is research only.'))}</i>"]
    return _cap("\n".join(lines))


def ops_alert(title: str, body: str) -> str:
    return _cap(f"<b>OPS: {e(title)}</b>\n{e(body)}")


def _cap(s: str) -> str:
    return s if len(s) <= MAX_LEN else s[: MAX_LEN - 20] + "\n…(truncated)"
