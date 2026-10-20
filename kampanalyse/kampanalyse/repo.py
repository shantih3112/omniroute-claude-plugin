"""Lese-/skrivefunksjoner mot databasen for kamper, forslag, bonger og utsendingskø."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .analysis import Candidate
from .coupons import CouponDraft
from .db import DB
from .providers.base import Fixture
from .timeutil import OSLO, from_iso, local, local_date, to_iso


def upsert_fixture(db: DB, fx: Fixture, now: datetime) -> None:
    db.execute(
        """INSERT INTO fixtures(id,local_date,league_id,league_name,season,kickoff,home,away,status,referee,venue,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET kickoff=excluded.kickoff, status=CASE WHEN fixtures.final_confirmed_at IS NULL
             THEN excluded.status ELSE fixtures.status END, referee=excluded.referee, updated_at=excluded.updated_at""",
        (fx.id, local_date(fx.kickoff).isoformat(), fx.league_id, fx.league_name, fx.season, to_iso(fx.kickoff),
         fx.home, fx.away, fx.status, fx.referee, fx.venue, to_iso(now)))


def fixture_from_row(r) -> Fixture:
    return Fixture(r["id"], r["league_id"], r["league_name"], r["season"], from_iso(r["kickoff"]), r["home"], r["away"],
                   r["status"], r["referee"], r["venue"])


def new_run(db: DB, kind: str, d: date, now: datetime, model_version: str) -> int:
    cur = db.execute("INSERT INTO runs(kind,local_date,started_at,status,model_version) VALUES(?,?,?,?,?)",
                     (kind, d.isoformat(), to_iso(now), "running", model_version))
    return int(cur.lastrowid)


def finish_run(db: DB, run_id: int, status: str, now: datetime, notes: dict) -> None:
    db.execute("UPDATE runs SET status=?, finished_at=?, notes_json=? WHERE id=?",
               (status, to_iso(now), json.dumps(notes, ensure_ascii=False), run_id))


def _next_seq(db: DB, like: str) -> int:
    r = db.one("SELECT COUNT(DISTINCT id) AS n FROM (SELECT id FROM picks WHERE id LIKE ? UNION SELECT id FROM coupons WHERE id LIKE ?)",
               (like, like))
    return int(r["n"]) + 1


def save_pick(db: DB, run_id: int, c: Candidate, rank: int, model_version: str, d: date) -> str:
    prefix = f"E-{d:%y%m%d}-"
    pid = f"{prefix}{_next_seq(db, prefix + '%'):02d}"
    db.execute(
        """INSERT INTO picks(id,run_id,fixture_id,selection_key,label,odds,odds_source,odds_kind,odds_checked_at,ref_odds,
             market_q,model_q,final_q,p_void,unc,ev_point,ev_cons,min_odds,quality,tags_json,analysis_json,rank,model_version)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, run_id, c.fixture.id, c.selection.key(), c.label, c.odds, c.odds_source, c.odds_kind,
         to_iso(c.odds_checked_at), c.ref_odds, c.market_q, c.model_q, c.final_q, c.push, c.unc, c.ev_point, c.ev_cons,
         c.min_odds, c.quality, json.dumps(c.tags), json.dumps(c.analysis, ensure_ascii=False, default=str), rank,
         model_version))
    return pid


def save_coupon(db: DB, run_id: int, d: date, draft: CouponDraft, pick_ids: list[str], now: datetime) -> str:
    prefix = f"K-{d:%y%m%d}-{draft.band.code}"
    cid = f"{prefix}{_next_seq(db, prefix + '%')}"
    status = "KONTROLLERT" if draft.verified_nt else "FORELØPIG"
    db.execute(
        """INSERT INTO coupons(id,version,run_id,band,title,status,total_odds,total_verified,hit_est,ev_est,odds_checked_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, 1, run_id, draft.band.code, draft.band.title, status, draft.total_odds, int(draft.verified_nt),
         draft.hit_est, draft.ev_est, to_iso(min(c.odds_checked_at for c in draft.legs))))
    for i, pid in enumerate(pick_ids):
        db.execute("INSERT INTO coupon_legs(coupon_id,version,idx,pick_id) VALUES(?,?,?,?)", (cid, 1, i, pid))
    db.log_change(to_iso(now), "coupon", cid, "opprettet", {"versjon": 1, "ledd": pick_ids})
    return cid


@dataclass
class PickView:
    row: dict
    fixture: dict

    def __getitem__(self, k):
        return self.row[k]

    @property
    def analysis(self) -> dict:
        return json.loads(self.row["analysis_json"])

    @property
    def tags(self) -> list[str]:
        return json.loads(self.row["tags_json"])


def pick(db: DB, pid: str) -> PickView | None:
    r = db.one("SELECT * FROM picks WHERE id=?", (pid,))
    if not r:
        return None
    f = db.one("SELECT * FROM fixtures WHERE id=?", (r["fixture_id"],))
    return PickView(dict(r), dict(f))


def coupon_latest(db: DB, cid: str) -> dict | None:
    r = db.one("SELECT * FROM coupons WHERE id=? ORDER BY version DESC LIMIT 1", (cid,))
    return dict(r) if r else None


def coupon_legs(db: DB, cid: str, version: int) -> list[PickView]:
    rows = db.all("SELECT pick_id FROM coupon_legs WHERE coupon_id=? AND version=? ORDER BY idx", (cid, version))
    return [p for p in (pick(db, r["pick_id"]) for r in rows) if p]


def coupons_for_date(db: DB, d: date, published_only: bool = True) -> list[dict]:
    rows = db.all(
        """SELECT c.* FROM coupons c JOIN runs r ON r.id=c.run_id
           WHERE r.local_date=? AND c.superseded=0 {} ORDER BY c.band, c.id""".format(
            "AND c.published_at IS NOT NULL" if published_only else ""), (d.isoformat(),))
    return [dict(r) for r in rows]


def picks_for_date(db: DB, d: date, published_only: bool = True) -> list[PickView]:
    rows = db.all(
        """SELECT p.id FROM picks p JOIN runs r ON r.id=p.run_id WHERE r.local_date=? {}
           ORDER BY p.run_id, p.rank""".format("AND p.published_at IS NOT NULL" if published_only else ""),
        (d.isoformat(),))
    return [p for p in (pick(db, r["id"]) for r in rows) if p]


def supersede_coupon(db: DB, cid: str, new_status: str | None, now: datetime, reason: str,
                     total_odds: float | None = None, total_verified: bool | None = None) -> int:
    """Lag ny versjon av bongen (gamle versjoner beholdes)."""
    cur = coupon_latest(db, cid)
    assert cur
    v = cur["version"] + 1
    legs = db.all("SELECT idx, pick_id FROM coupon_legs WHERE coupon_id=? AND version=?", (cid, cur["version"]))
    with db.tx():
        db.execute("UPDATE coupons SET superseded=1 WHERE id=? AND version=?", (cid, cur["version"]))
        db.execute(
            """INSERT INTO coupons(id,version,run_id,band,title,status,outcome,total_odds,total_verified,hit_est,ev_est,
                 published_at,odds_checked_at,superseded,settled_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)""",
            (cid, v, cur["run_id"], cur["band"], cur["title"], new_status or cur["status"], cur["outcome"],
             total_odds if total_odds is not None else cur["total_odds"],
             int(total_verified) if total_verified is not None else cur["total_verified"], cur["hit_est"],
             cur["ev_est"], cur["published_at"], to_iso(now), cur["settled_at"]))
        for l in legs:
            db.execute("INSERT INTO coupon_legs(coupon_id,version,idx,pick_id) VALUES(?,?,?,?)",
                       (cid, v, l["idx"], l["pick_id"]))
        db.log_change(to_iso(now), "coupon", cid, "ny_versjon", {"versjon": v, "grunn": reason})
    return v


# --- utsendingskø (duplikatbeskyttelse) ---

def in_quiet(user: dict, now: datetime) -> datetime | None:
    """Returnerer UTC-tidspunkt stilleperioden slutter, eller None."""
    qs, qe = user.get("quiet_start"), user.get("quiet_end")
    if not qs or not qe:
        return None
    l = local(now)
    s = time.fromisoformat(qs)
    e = time.fromisoformat(qe)
    t = l.time()
    inside = (s <= t < e) if s < e else (t >= s or t < e)
    if not inside:
        return None
    end_day = l.date() if t < e else l.date() + timedelta(days=1)
    return datetime.combine(end_day, e, tzinfo=OSLO)


def enqueue(db: DB, dedupe_key: str, chat_id: int, text: str, markup: list | None, now: datetime,
            not_before: datetime | None = None, pin: bool = False) -> bool:
    cur = db.execute(
        """INSERT OR IGNORE INTO outbox(dedupe_key,chat_id,text,markup_json,not_before,pin,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (dedupe_key, chat_id, text, json.dumps(markup) if markup else None,
         to_iso(not_before) if not_before else None, int(pin), to_iso(now)))
    return cur.rowcount == 1
