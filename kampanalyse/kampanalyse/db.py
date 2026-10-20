"""SQLite-lagring. Én fil på varig volum; WAL-modus for robusthet ved omstart.

Prinsipp: forslag og bonger slettes aldri. Endringer gir ny versjon eller en rad i
`changes`, slik at historikken er etterprøvbar.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    name TEXT,
    role TEXT NOT NULL CHECK (role IN ('owner','admin','reader')),
    brief_time TEXT NOT NULL DEFAULT '08:00',
    quiet_start TEXT,
    quiet_end TEXT,
    notify_level TEXT NOT NULL DEFAULT 'normal',
    leagues_json TEXT,
    categories_json TEXT,
    paused INTEGER NOT NULL DEFAULT 0,
    budget_month REAL,
    daily_limit REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    id TEXT PRIMARY KEY,
    local_date TEXT NOT NULL,
    league_id INTEGER,
    league_name TEXT,
    season INTEGER,
    kickoff TEXT NOT NULL,
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NS',
    elapsed INTEGER,
    referee TEXT,
    venue TEXT,
    live_json TEXT,
    live_at TEXT,
    final_json TEXT,
    final_first_seen TEXT,
    final_confirmed_at TEXT,
    corrected_at TEXT,
    lineups_json TEXT,
    lineups_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fixtures_date ON fixtures(local_date);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    local_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    model_version TEXT,
    notes_json TEXT
);

CREATE TABLE IF NOT EXISTS picks (
    id TEXT PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    fixture_id TEXT NOT NULL REFERENCES fixtures(id),
    selection_key TEXT NOT NULL,
    label TEXT NOT NULL,
    odds REAL NOT NULL,
    odds_source TEXT NOT NULL,
    odds_kind TEXT NOT NULL,
    odds_checked_at TEXT NOT NULL,
    ref_odds REAL,
    market_q REAL,
    model_q REAL,
    final_q REAL NOT NULL,
    p_void REAL NOT NULL DEFAULT 0,
    unc REAL NOT NULL,
    ev_point REAL NOT NULL,
    ev_cons REAL NOT NULL,
    min_odds REAL NOT NULL,
    quality REAL NOT NULL,
    tags_json TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    rank INTEGER,
    model_version TEXT NOT NULL,
    published_at TEXT,
    closing_odds REAL,
    closing_checked_at TEXT,
    live_state TEXT,
    result TEXT,
    result_confirmed_at TEXT,
    withdrawn_at TEXT,
    withdrawn_reason TEXT
);
CREATE INDEX IF NOT EXISTS picks_fixture ON picks(fixture_id);

CREATE TABLE IF NOT EXISTS coupons (
    id TEXT NOT NULL,
    version INTEGER NOT NULL,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    band TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    outcome TEXT,
    total_odds REAL NOT NULL,
    total_verified INTEGER NOT NULL DEFAULT 0,
    hit_est REAL,
    ev_est REAL,
    published_at TEXT,
    odds_checked_at TEXT,
    superseded INTEGER NOT NULL DEFAULT 0,
    settled_at TEXT,
    PRIMARY KEY (id, version)
);

CREATE TABLE IF NOT EXISTS coupon_legs (
    coupon_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    pick_id TEXT NOT NULL REFERENCES picks(id),
    PRIMARY KEY (coupon_id, version, idx)
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL UNIQUE,
    chat_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    markup_json TEXT,
    not_before TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    pin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    tg_message_id INTEGER
);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(status);

CREATE TABLE IF NOT EXISTS user_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    ref_id TEXT NOT NULL,
    stake REAL NOT NULL,
    odds REAL NOT NULL,
    placed_at TEXT NOT NULL,
    local_date TEXT NOT NULL,
    returned REAL,
    settled_at TEXT
);

CREATE TABLE IF NOT EXISTS nt_odds_manual (
    fixture_id TEXT NOT NULL,
    selection_key TEXT NOT NULL,
    odds REAL NOT NULL,
    entered_by INTEGER NOT NULL,
    entered_at TEXT NOT NULL,
    PRIMARY KEY (fixture_id, selection_key, entered_at)
);

CREATE TABLE IF NOT EXISTS live_events (
    fixture_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    minute INTEGER,
    type TEXT,
    detail TEXT,
    team TEXT,
    player TEXT,
    PRIMARY KEY (fixture_id, event_key)
);

CREATE TABLE IF NOT EXISTS health (
    source TEXT PRIMARY KEY,
    last_ok TEXT,
    last_error TEXT,
    last_error_at TEXT,
    outage_since TEXT
);

CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class DB:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.conn.executescript(SCHEMA)

    # --- grunnleggende ---
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, tuple(params))

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def tx(self):
        return _Tx(self)

    # --- kv ---
    def kv_get(self, key: str) -> str | None:
        r = self.one("SELECT value FROM kv WHERE key=?", (key,))
        return r["value"] if r else None

    def kv_set(self, key: str, value: str) -> None:
        self.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (key, value))

    def kv_claim(self, key: str, value: str) -> bool:
        """Atomisk 'første gang': True hvis nøkkelen ikke fantes. Brukes mot duplikatkjøring."""
        cur = self.execute("INSERT OR IGNORE INTO kv(key,value) VALUES(?,?)", (key, value))
        return cur.rowcount == 1

    def log_change(self, ts: str, entity: str, entity_id: str, kind: str, detail: Any = None) -> None:
        self.execute("INSERT INTO changes(ts,entity,entity_id,kind,detail) VALUES(?,?,?,?,?)",
                     (ts, entity, entity_id, kind, json.dumps(detail, ensure_ascii=False) if detail is not None else None))


class _Tx:
    def __init__(self, db: DB):
        self.db = db

    def __enter__(self):
        self.db.lock.acquire()
        self.db.conn.execute("BEGIN IMMEDIATE")
        return self.db

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.db.conn.execute("COMMIT")
            else:
                self.db.conn.execute("ROLLBACK")
        finally:
            self.db.lock.release()
        return False
