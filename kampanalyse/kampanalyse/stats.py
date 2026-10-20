"""Åpen historikk: treff, simulert yield, største fall, per marked og oddskategori.

Simulering: 1 enhet per publisert forslag (flat). Holdes atskilt fra brukerregistrerte spill.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from .coupons import BAND_BY_CODE
from .db import DB
from .markets import MARKET_GROUP, Result, payout_factor
from .repo import coupon_legs


def coupon_return(legs) -> float | None:
    """Retur per enhet, eller None hvis ikke alle ledd er avgjort (og ingen er tapt)."""
    factors = []
    for p in legs:
        if p["result"] is None:
            if any(x["result"] == "LOST" for x in legs):
                return 0.0
            return None
        factors.append(payout_factor(Result(p["result"]), p["odds"]))
    return math.prod(factors)


def coupon_outcome(legs) -> str | None:
    if any(p["result"] == "LOST" for p in legs):
        return "LOST"
    if any(p["result"] is None for p in legs):
        return None
    rs = {p["result"] for p in legs}
    if rs == {"WON"}:
        return "WON"
    if rs == {"VOID"}:
        return "VOID"
    return "PARTIAL"


def _agg(items: list[tuple[str, float]]) -> dict:
    """items: (utfall, retur per enhet) i kronologisk rekkefølge."""
    won = sum(1 for o, _ in items if o in ("WON", "HALF_WON"))
    lost = sum(1 for o, _ in items if o in ("LOST", "HALF_LOST"))
    void = sum(1 for o, _ in items if o == "VOID")
    n = len(items)
    net = sum(r - 1 for _, r in items)
    peak = cur = dd = 0.0
    for _, r in items:
        cur += r - 1
        peak = max(peak, cur)
        dd = max(dd, peak - cur)
    decided = won + lost
    return {"n": n, "won": won, "lost": lost, "void": void, "hit": won / decided if decided else None,
            "net": net, "yield": net / n if n else 0.0, "max_dd": dd}


def overall(db: DB, since: date | None = None, until: date | None = None) -> dict:
    cond, params = "", []
    if since:
        cond += " AND r.local_date>=?"
        params.append(since.isoformat())
    if until:
        cond += " AND r.local_date<=?"
        params.append(until.isoformat())
    # rank ≤ 50 = publiserte enkeltspill; rank > 100 = ledd som bare inngår i bonger
    picks = db.all(f"""SELECT p.*, f.kickoff FROM picks p JOIN runs r ON r.id=p.run_id JOIN fixtures f ON f.id=p.fixture_id
                       WHERE p.published_at IS NOT NULL AND p.rank<=50 {cond}
                       ORDER BY f.kickoff""", params)
    singles_items, by_market, open_s = [], defaultdict(list), 0
    clv = []
    for p in picks:
        if p["result"] is None:
            open_s += 1
            continue
        r = payout_factor(Result(p["result"]), p["odds"])
        singles_items.append((p["result"], r))
        by_market[MARKET_GROUP.get(p["selection_key"].split(":")[0], "Annet")].append((p["result"], r))
        if p["closing_odds"]:
            clv.append(p["odds"] / p["closing_odds"] - 1)
    coupons = db.all(f"""SELECT c.* FROM coupons c JOIN runs r ON r.id=c.run_id
                         WHERE c.superseded=0 AND c.published_at IS NOT NULL {cond} ORDER BY c.published_at""", params)
    c_items, by_band, open_c = [], defaultdict(list), 0
    for c in coupons:
        legs = coupon_legs(db, c["id"], c["version"])
        ret = coupon_return(legs)
        out = coupon_outcome(legs)
        if ret is None or out is None:
            open_c += 1
            continue
        oc = "WON" if out == "WON" else "LOST" if out == "LOST" else "VOID" if out == "VOID" else ("WON" if ret > 1 else "LOST")
        c_items.append((oc, ret))
        by_band[BAND_BY_CODE[c["band"]].title].append((oc, ret))
    s = {"singles": {**_agg(singles_items), "open": open_s}, "coupons": {**_agg(c_items), "open": open_c},
         "by_market": {k: _agg(v) for k, v in by_market.items()}, "by_band": {k: _agg(v) for k, v in by_band.items()},
         "clv": sum(clv) / len(clv) if clv else None, "clv_n": len(clv)}
    s["sim_net"] = s["singles"]["net"] + s["coupons"]["net"]
    return s


def personal(db: DB, chat_id: int) -> dict | None:
    rows = db.all("SELECT * FROM user_bets WHERE chat_id=?", (chat_id,))
    if not rows:
        return None
    stake = sum(r["stake"] for r in rows)
    ret = sum(r["returned"] or 0 for r in rows if r["returned"] is not None)
    settled_stake = sum(r["stake"] for r in rows if r["returned"] is not None)
    return {"n": len(rows), "stake": stake, "ret": ret, "net": ret - settled_stake,
            "open": sum(1 for r in rows if r["returned"] is None)}
