# Architecture

```
             research (offline)                               service (online, one process + watchdog)
 ┌──────────────────────────────┐            ┌────────────────────────────────────────────────────────────┐
 │ data/loaders  → data/quality │            │ live/feeds (OANDA | Replay) ─ completed M1 bars            │
 │ data/resample (NY-close D1)  │            │   └→ data/quality.check_live_bar  (gate, per symbol)       │
 │ strategies/library  ─────────┼─ same ────►│   └→ live/aggregate (M1→H1 incremental)                    │
 │ backtest/engine (bid/ask,    │   code     │        └→ strategies/library on completed H1 bars          │
 │   stop-first, delay, gaps)   │            │             └→ no-trade policy (data, hours, holidays,     │
 │ backtest/metrics (bootstrap, │            │                calendar blackout, processing lag)          │
 │   DSR)  backtest/portfolio   │            │             └→ risk/engine (independent, config-only)      │
 │ research/runner → registry   │            │                  └→ signals/store (immutable + events)     │
 │ risk/ftmo  research/planner  │            │                       └→ telegram/format → outbox (dedupe) │
 └──────────────────────────────┘            │ signals/lifecycle: paper tracking each M1 bar (=engine)    │
                                             │ news/calendar (hourly, fail-closed)                        │
                                             │ telegram/admin (authorised IDs)   health + heartbeat       │
                                             └────────────────────────────────────────────────────────────┘
                                                     ops/watchdog (separate process) · dead-man ping
```

Module boundaries (one responsibility each): ingestion `data/`, features `features.py`,
strategies `strategies/`, backtesting `backtest/`, portfolio limits `backtest/portfolio.py` +
`risk/engine.py`, risk `risk/`, storage `signals/store.py`, delivery `telegram/`, monitoring
`ops/` + `live/service.health()`. **Execution: deliberately absent.**

## Key design decisions
* **One code path for research and live.** Strategies are pure functions of completed bars;
  the live service calls the same `generate()` on a rolling window, and the paper tracker
  replicates the engine's fill rules (parity test). Truncation tests guard against look-ahead.
* **Database-enforced integrity.** SQLite (WAL) triggers make signals immutable and events
  append-only; outbox dedupe keys make delivery idempotent across restarts; signal IDs are
  deterministic (`yymmdd-HHMM-SYMBOL-STRAT`), so re-processing a bar cannot create a duplicate.
* **Fail closed.** Stale data, unknown calendar, DB errors, kill switch, pause → no new signals;
  tracking of existing signals continues whenever prices are available.
* **Risk engine above strategies.** Limits come only from config; risk per trade can only be
  reduced by losing streaks; martingale/grids/doubling/target-chasing cannot be expressed.
* **Honest labels.** Every message carries its evidence class; replay output is tagged `[REPLAY]`;
  hypothetical, paper and live results are never mixed.

## AI / LLM policy
No LLM is used anywhere in the current system. If one is added (e.g. to summarise central-bank
headlines), it must: receive retrieved text as untrusted data; return a structured object
(source URL, timestamp, currencies, event type) validated by code; be unable to touch config,
risk limits, credentials or permissions; never produce prices or trade decisions; log model
version and prompt hash; and degrade to "no summary" when unavailable. Numbers, sizing and rule
checks stay deterministic.

## Monitoring for deterioration (pre-set, see SCORECARD §6)
Forward paper results are stored per evidence class. Investigate at the 90th percentile of the
bootstrap drawdown distribution for the same trade count or if realised spreads exceed the model
by > 50 % over 20 trades; pause at the 99th percentile or any integrity incident. No automatic
retraining; strategy changes are new versions that go through the gates again.

## Schema & migrations
`signals/store.py` holds the schema (`SCHEMA_VERSION` in table `meta`). Migrations: add a new
numbered SQL block, apply it in `Store.__init__` when `meta.schema_version` is lower, back up
first (`fxsignal backup`). Never rewrite `signals`/`events` rows; add columns or new tables.
