"""SQLite persistence: immutable signals, append-only lifecycle events, outbox, state, bars.

Integrity rules are enforced by the database itself (triggers), not just by convention:
* a signal row can never be UPDATEd or DELETEd;
* lifecycle events can never be UPDATEd or DELETEd;
* outbox rows are unique per dedupe key, so a restart cannot send the same message twice.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side INTEGER NOT NULL CHECK (side IN (-1, 1)),
  strategy TEXT NOT NULL,
  strategy_version TEXT NOT NULL,
  evidence_class TEXT NOT NULL CHECK (evidence_class IN ('research', 'paper_forward', 'holdout_confirmed')),
  entry_type TEXT NOT NULL,
  entry_ref REAL NOT NULL,
  zone_lo REAL NOT NULL,
  zone_hi REAL NOT NULL,
  stop REAL NOT NULL,
  target REAL,
  max_hold_min REAL NOT NULL,
  expires_at TEXT NOT NULL,
  risk_pct REAL NOT NULL,
  est_cost_r REAL NOT NULL,
  rr_after_costs REAL,
  context TEXT NOT NULL,
  rationale TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS signals_immutable_u BEFORE UPDATE ON signals
BEGIN SELECT RAISE(ABORT, 'signals are immutable'); END;
CREATE TRIGGER IF NOT EXISTS signals_immutable_d BEFORE DELETE ON signals
BEGIN SELECT RAISE(ABORT, 'signals are immutable'); END;
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id TEXT NOT NULL REFERENCES signals(id),
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  price REAL,
  r_result REAL,
  detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_sig ON events(signal_id, seq);
CREATE TRIGGER IF NOT EXISTS events_append_only_u BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_append_only_d BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dedupe_key TEXT NOT NULL UNIQUE,
  channel TEXT NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT,
  last_error TEXT,
  tg_message_id INTEGER,
  accepted_at TEXT
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(status, id);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bars (
  symbol TEXT NOT NULL, tf TEXT NOT NULL, t TEXT NOT NULL,
  o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL, v REAL,
  spread REAL, PRIMARY KEY (symbol, tf, t)
);
CREATE TABLE IF NOT EXISTS calendar (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, currency TEXT NOT NULL,
  impact TEXT NOT NULL, scheduled_at TEXT NOT NULL, forecast TEXT, previous TEXT, actual TEXT,
  first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS incidents (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL
);
"""

TERMINAL = {"cancelled", "expired", "closed", "missed", "data_gap"}


@dataclass
class SignalRecord:
    id: str
    created_at: str
    symbol: str
    side: int
    strategy: str
    strategy_version: str
    evidence_class: str
    entry_type: str
    entry_ref: float
    zone_lo: float
    zone_hi: float
    stop: float
    target: float | None
    max_hold_min: float
    expires_at: str
    risk_pct: float
    est_cost_r: float
    rr_after_costs: float | None
    context: dict = field(default_factory=dict)
    rationale: str = ""

    def payload_hash(self) -> str:
        d = asdict(self)
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

    @contextmanager
    def tx(self):
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    # ---- signals & events ---------------------------------------------------------------
    def add_signal(self, s: SignalRecord, now: str) -> bool:
        """Insert a new signal + 'created' event atomically. Returns False if the id exists."""
        d = asdict(s)
        d["context"] = json.dumps(s.context, sort_keys=True, default=str)
        d["payload_sha256"] = s.payload_hash()
        cols = ",".join(d)
        q = ",".join("?" for _ in d)
        with self.tx() as c:
            if c.execute("SELECT 1 FROM signals WHERE id=?", (s.id,)).fetchone():
                return False
            c.execute(f"INSERT INTO signals ({cols}) VALUES ({q})", tuple(d.values()))
            c.execute("INSERT INTO events (signal_id, ts, kind, detail) VALUES (?,?,?,?)",
                      (s.id, now, "created", "{}"))
        return True

    def add_event(self, signal_id: str, ts: str, kind: str, price: float | None = None,
                  r_result: float | None = None, detail: dict | None = None) -> None:
        with self.tx() as c:
            last = c.execute("SELECT kind FROM events WHERE signal_id=? ORDER BY seq DESC LIMIT 1",
                             (signal_id,)).fetchone()
            if last is None:
                raise KeyError(signal_id)
            if last["kind"] in TERMINAL:
                raise ValueError(f"signal {signal_id} already {last['kind']}")
            c.execute("INSERT INTO events (signal_id, ts, kind, price, r_result, detail) VALUES (?,?,?,?,?,?)",
                      (signal_id, ts, kind, price, r_result, json.dumps(detail or {}, default=str)))

    def signal(self, signal_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        return dict(r) if r else None

    def events(self, signal_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM events WHERE signal_id=? ORDER BY seq",
                                                   (signal_id,))]

    def state(self, signal_id: str) -> str:
        r = self.conn.execute("SELECT kind FROM events WHERE signal_id=? AND kind NOT IN ('published','note') "
                              "ORDER BY seq DESC LIMIT 1", (signal_id,)).fetchone()
        return r["kind"] if r else "unknown"

    def active_signals(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM signals ORDER BY created_at").fetchall()
        out = []
        for r in rows:
            st = self.state(r["id"])
            if st not in TERMINAL:
                d = dict(r)
                d["state"] = st
                out.append(d)
        return out

    def signals_between(self, a: str, b: str) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM signals WHERE created_at >= ? AND created_at < ? ORDER BY created_at",
                                 (a, b)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["state"] = self.state(r["id"])
            ev = self.events(r["id"])
            closes = [e for e in ev if e["kind"] == "closed"]
            d["r_result"] = closes[-1]["r_result"] if closes else None
            out.append(d)
        return out

    def closed_results(self, evidence_class: str | None = None) -> list[dict]:
        q = ("SELECT s.id, s.symbol, s.strategy, s.evidence_class, e.ts, e.r_result FROM events e "
             "JOIN signals s ON s.id = e.signal_id WHERE e.kind='closed'")
        args: tuple = ()
        if evidence_class:
            q += " AND s.evidence_class=?"
            args = (evidence_class,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY e.ts", args)]

    # ---- outbox ---------------------------------------------------------------------------
    def enqueue(self, dedupe_key: str, channel: str, kind: str, text: str, now: str) -> bool:
        with self.tx() as c:
            cur = c.execute("INSERT OR IGNORE INTO outbox (dedupe_key, channel, kind, text, created_at, next_attempt_at) "
                            "VALUES (?,?,?,?,?,?)", (dedupe_key, channel, kind, text, now, now))
            return cur.rowcount == 1

    def due_outbox(self, now: str, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM outbox WHERE status='pending' AND next_attempt_at <= ? ORDER BY id LIMIT ?", (now, limit))]

    def mark_sent(self, oid: int, msg_id: int | None, now: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE outbox SET status='accepted', tg_message_id=?, accepted_at=?, attempts=attempts+1 "
                      "WHERE id=?", (msg_id, now, oid))

    def mark_retry(self, oid: int, err: str, next_at: str, give_up: bool = False) -> None:
        with self.tx() as c:
            c.execute("UPDATE outbox SET status=?, last_error=?, next_attempt_at=?, attempts=attempts+1 WHERE id=?",
                      ("failed" if give_up else "pending", err[:500], next_at, oid))

    def outbox_stats(self) -> dict:
        return {r["status"]: r["n"] for r in self.conn.execute("SELECT status, COUNT(*) n FROM outbox GROUP BY status")}

    # ---- kv / incidents / bars / calendar -----------------------------------------------------
    def kv_get(self, key: str, default=None):
        r = self.conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def kv_set(self, key: str, value, now: str) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO kv VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                      "updated_at=excluded.updated_at", (key, json.dumps(value, default=str), now))

    def incident(self, ts: str, kind: str, detail: str) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO incidents (ts, kind, detail) VALUES (?,?,?)", (ts, kind, detail[:2000]))

    def incidents_since(self, ts: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM incidents WHERE ts >= ? ORDER BY seq", (ts,))]

    def upsert_bars(self, symbol: str, tf: str, rows: list[tuple]) -> None:
        with self.tx() as c:
            c.executemany("INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?,?)",
                          [(symbol, tf, *r) for r in rows])

    def load_bars(self, symbol: str, tf: str, since: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT t,o,h,l,c,v,spread FROM bars WHERE symbol=? AND tf=?"
        args: tuple = (symbol, tf)
        if since:
            q += " AND t >= ?"
            args += (since,)
        return self.conn.execute(q + " ORDER BY t", args).fetchall()

    def prune_bars(self, before: str) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM bars WHERE t < ?", (before,))

    def upsert_calendar(self, ev: dict, now: str) -> str:
        """Insert or revise a calendar event; returns 'new', 'revised' or 'same'."""
        with self.tx() as c:
            old = c.execute("SELECT * FROM calendar WHERE id=?", (ev["id"],)).fetchone()
            if old is None:
                c.execute("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                          (ev["id"], ev["source"], ev["title"], ev["currency"], ev["impact"], ev["scheduled_at"],
                           ev.get("forecast"), ev.get("previous"), ev.get("actual"), now, now))
                return "new"
            changed = any(str(old[k]) != str(ev.get(k)) for k in ("scheduled_at", "impact", "forecast", "actual"))
            c.execute("UPDATE calendar SET scheduled_at=?, impact=?, forecast=?, previous=?, actual=?, last_seen_at=?, "
                      "revision=revision+? WHERE id=?",
                      (ev["scheduled_at"], ev["impact"], ev.get("forecast"), ev.get("previous"), ev.get("actual"), now,
                       1 if changed else 0, ev["id"]))
            return "revised" if changed else "same"

    def calendar_between(self, a: str, b: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM calendar WHERE scheduled_at >= ? AND scheduled_at <= ? ORDER BY scheduled_at", (a, b))]

    def backup(self, dest: str | Path) -> None:
        """Consistent online backup (SQLite backup API)."""
        dst = sqlite3.connect(str(dest))
        with self._lock:
            self.conn.backup(dst)
        dst.close()
