# fxsignal — paper-first forex research, risk and Telegram signal system

**Current verdict (2026-10-20): the software is built and tested; no strategy has shown a
credible edge, so the service runs in research mode and sends nothing to anyone but the admin.**
Read [docs/STATUS.md](docs/STATUS.md) first.

This is not financial advice and not a promise of profit. Live order execution is not implemented.

## What is here
| Area | Where | State |
|---|---|---|
| Pre-registered quality gates | [docs/SCORECARD.md](docs/SCORECARD.md) | committed before any backtest |
| Data from 4 vendor mirrors, cross-checked | [docs/DATA.md](docs/DATA.md), `scripts/data_audit.py` | done |
| Backtester (bid/ask, costs, stop-first, gaps, follower delay, missed entries) | `src/fxsignal/backtest/` | done, unbiased on random entries |
| 13 strategy families, 40 configurations, every run logged | [docs/STRATEGIES.md](docs/STRATEGIES.md), [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md), `research/registry.jsonl` | all failed Gate R |
| Independent risk engine + sizing | `src/fxsignal/risk/` | done |
| FTMO profile, boundary tests, pass-rate study | [docs/FTMO.md](docs/FTMO.md) | rules UNVERIFIED → challenge use blocked |
| Paper service: feed → quality gate → strategies → no-trade policy → risk → immutable signal → Telegram outbox; lifecycle; daily reports; admin commands | `src/fxsignal/live/`, `signals/`, `telegram/`, `news/` | done; tested with replayed real data and a mocked Telegram API |
| Watchdog, systemd/Docker, backups, runbook | [docs/OPERATIONS.md](docs/OPERATIONS.md), `deploy/` | prepared, **not deployed** |
| Sharing & legal questions | [docs/SHARING_AND_COMPLIANCE.md](docs/SHARING_AND_COMPLIANCE.md) | private only |
| Capital planning (assumed returns) | `fxsignal plan`, `src/fxsignal/research/planner.py` | done |

## Quick start (local)
```bash
cd fxsignal
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt && .venv/bin/pip install --no-deps -e .
.venv/bin/python -m pytest                      # 61 tests, ~3 min, no network or market data needed
.venv/bin/fxsignal size EURUSD 10000 USD 0.5 1.0850 1.0820
.venv/bin/fxsignal plan --start 1000 --monthly 100 --exp-r 0.0   # assumed returns only
```
Research reproduction (needs the vendor mirrors in `data/raw/`, see DATA.md):
```bash
.venv/bin/python scripts/data_audit.py
.venv/bin/python scripts/gate_r.py              # round 1+2 grids, development split
.venv/bin/python scripts/gate_r_xau.py
.venv/bin/python scripts/seasonality.py
.venv/bin/python scripts/ftmo_and_planning.py
.venv/bin/fxsignal replay --start 2026-09-14 --days 3 --strategies trend_pullback --capture /tmp/msgs.txt
```
Live paper service: see [docs/OPERATIONS.md](docs/OPERATIONS.md) (needs an OANDA practice token,
a Telegram bot, and a VPS).
