# Requirements, open questions and working assumptions

Status as of 2026-10-20. Each assumption is used until the owner answers the matching question.

| # | Question (affects implementation) | Working assumption | Where it matters |
|---|---|---|---|
| 1 | Broker / platform supplying live prices? | None connected. Research uses public vendor mirrors (docs/DATA.md). Live adapter written for **OANDA v20 REST** (free practice account works on Linux). An MT5 bridge is not possible on Linux without Wine/Windows. | `live/feeds.py` |
| 2 | Account size and currency? | Illustrative **10,000 USD**; sizing tool accepts any. EUR/NOK accounts need a conversion rate feed (supported in code). | `risk/sizing.py` |
| 3 | Monthly budget (hosting, data, news)? | ≤ 15 USD/month: one small VPS (2 vCPU / 2–4 GB). Free calendar source; no paid news. | deployment |
| 4 | Instruments and sessions? | 11 liquid FX majors/minors; XAUUSD optional and evaluated separately. London + New York sessions prioritised; Asia allowed only where validated. | `instruments.py`, strategies |
| 5 | Risk limits? | 0.5 % risk/trade (max 1 %), 2 % total open risk, 1 % per-currency net exposure, 3 % daily stop, 8 % overall stop (FTMO buffers tighter). | `config/default.yaml` |
| 6 | Exact FTMO product, account type, stage? | **FTMO 2-Step Challenge, Standard account, Phase 1**. Rules could not be read from ftmo.com from this environment (host unreachable) → profile marked **UNVERIFIED** and challenge use is blocked until verified. | `config/ftmo/` |
| 7 | Read-only account access available? | No. Signals carry suggested sizes only; the system does **not** claim account-wide risk enforcement. | risk engine |
| 8 | Hosting and Telegram credentials? | None provided. Code runs locally/paper; deployment files prepared, not deployed. | `deploy/` |

## Defaults that stay on until changed explicitly by the owner
* Signal-only, paper mode. Live execution is **not implemented**.
* Private Telegram delivery to the owner only; no invitations, no external publication.
* Conservative risk; prohibitions on martingale, grids, doubling, loss-recovery sizing.

## Services that need money, credentials or permissions
| Need | Option | Cost / requirement |
|---|---|---|
| Live prices (Linux) | OANDA v20 practice API token | Free account; token in env var |
| Prices from FTMO's own feed | MT5 terminal on Windows VPS + bridge | Windows VPS (~15–30 USD/mo); not built yet |
| Economic calendar | Free weekly JSON (Forex Factory export, unofficial) or paid API (e.g. Trading Economics) | Free source has no SLA; paid has licence cost |
| News headlines | RSS from central banks (Fed, ECB, BoE, BoJ, SNB, RBA, BoC) | Free; latency minutes |
| Telegram | Bot token from @BotFather, channel ID, admin user ID | Free |
| Hosting | Any VPS with systemd or Docker | ~5–15 USD/mo |
| Dead-man monitoring | healthchecks.io style ping | Free tier |
