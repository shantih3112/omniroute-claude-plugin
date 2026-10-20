# Status and readiness assessment — 2026-10-20

Plain answer first: **the software works and is tested; no trading edge has been found.** The
service can run as a paper/research monitor today once a price feed token is provided. It does
not, and must not yet, send trade signals to anyone but the admin.

## Stage table

| Stage | Acceptance criteria | Status | Evidence |
|---|---|---|---|
| A – requirements, architecture, data, paper scanner | Data from ≥2 independent vendors cross-checked; timezones verified; quality gate; scanner runs on real bars | **Done (code + replay)**. No live feed connected | `research/data_audit.json`, `scripts/data_audit.py`, `fxsignal replay`, tests |
| B – backtester, baselines, registry | Bid/ask, costs, stop-first, gaps, delays, missed entries; unbiased on random entries; every run logged | **Done** | `tests/test_engine.py` (14), bias check in RESEARCH_LOG, `research/registry.jsonl` |
| C – strategy evaluation, portfolio, risk | Pre-registered gates applied; risk engine independent and tested | **Done – result negative**: 0 of 40 configurations pass Gate R | `docs/RESEARCH_LOG.md`, `tests/test_risk.py` |
| D – Telegram signals, lifecycle, commands, reports | Immutable signals, append-only events, dedupe, rate limits, admin auth, daily report incl. abstentions | **Done (code, mocked Telegram)**. Not tested against the real Bot API (host blocked here) | `tests/test_service.py`, `tests/test_failures.py`, `research/replay_demo_messages.txt` |
| E – FTMO profile + boundary tests | Versioned rules with sources; boundary/DST/reset tests; pass-rate study with intervals | **Done, profile UNVERIFIED** → challenge use blocked in code | `config/ftmo/`, `tests/test_risk.py`, `research/ftmo_planning.json` |
| F – hosted deployment, monitoring, recovery | Service running on a host, watchdog, backups, verified restart | **Deployment prepared, NOT deployed** (no hosting access). Restart/recovery verified in tests only | `deploy/`, `Dockerfile`, `docs/OPERATIONS.md` |
| G – forward validation, readiness | ≥3 months and ≥50 closed forward signals for a candidate | **Not started** – there is no candidate to forward-test | — |

"Code implemented" ≠ "deployed" ≠ "operating". Only the first is true today. Nothing is
running in the background after this session.

## What the evidence says

* 13 strategy families / 40 configurations (trend, breakout, pullback, range reversion,
  volatility compression, session breakout, ICT-style liquidity sweep, time-series momentum,
  fix-timing, round numbers), tested on 11 pairs, 2012–2017, with realistic costs and a
  15-minute follower delay: **none has positive net expectancy**; most have gross expectancy
  ≈ 0 before costs. Bollinger fades and London-open breakouts are reliably negative.
* The engine is not the cause: random entries at zero cost average +0.02 R (sd 0.03).
* Validation (2018–2020) and both holdouts (2021–2026) are untouched by strategy selection and
  remain available for future pre-declared hypotheses (one disclosed operational replay used
  12 days of holdout B; see RESEARCH_LOG).
* FTMO: with live portfolio limits, the best research candidate passed a 120-day Phase-1
  window from ~7 % of historical start dates at 0.5 % risk (90 % CI 3–14 %). A **zero-edge**
  hypothetical stream at 1 % risk "passes" ~41 % of the time from variance alone while breaching
  ~51 % — pass rates are not evidence of skill.
* Small-account planning: with no edge, 10 years of 100/month deposits and 15/month costs
  ends below total deposits in ~82 % of simulated paths. A 0.01-lot minimum needs ≈ 410 USD
  for a 20-pip stop at 0.5 % risk.

## Readiness verdict
| Use | Ready? |
|---|---|
| Admin-only research/paper monitor (labelled research) | Yes, after OANDA token + Telegram bot are configured and a VPS is provisioned |
| Private paper feed of "validated" signals | **No** – nothing has passed the gates |
| Inviting other people | **No** |
| Real money / FTMO challenge | **No** – no edge; FTMO rules unverified |

## What would change the verdict
1. A new hypothesis, declared in RESEARCH_LOG before testing, that passes Gates R, V and M.
2. Then holdouts (once), then ≥ 3 months / ≥ 50 forward paper signals within the backtest's
   90 % interval. Only then is small-risk live trading even worth discussing.
