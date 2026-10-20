# FTMO profile, simulation and limits

**Compliance status: UNVERIFIED.** ftmo.com could not be reached from the build environment.
The profile `config/ftmo/2step_standard_phase1.yaml` (FTMO 2-Step Challenge, Standard account,
Phase 1 — assumed; please confirm your exact product, account type and stage) was assembled from
secondary sources that agree with each other. Because `verified: false`, the code refuses
challenge use (`FtmoProfile.challenge_use_allowed()`), and every report says so.

## Rules as modelled (to be checked line by line on ftmo.com)
| Rule | Value used | Source status | Notes / disagreements |
|---|---|---|---|
| Profit target | 10 % (Phase 1); Verification 5 % | secondary, consistent | |
| Max daily loss | 5 % of initial balance below the day-start balance | secondary | one source: reference is max(balance, equity) at day start — both bases are implemented |
| Daily reset | midnight Europe/Prague (CET/CEST) | secondary, consistent | DST-aware; tested |
| Max loss | 10 % of initial balance, static | secondary, consistent | 1-Step reportedly trailing — not modelled |
| Floating P/L, commissions, swaps | count toward both loss limits | secondary | sim assumes all open trades sit at their MAE at once (conservative) |
| Minimum trading days | 4 | secondary | |
| Best-day / consistency | not applied to 2-Step | secondary | 1-Step reportedly 50 % best-day rule |
| News trading | 2-minute restriction on **funded Standard** accounts, not evaluation | secondary | system's own blackout is stricter (30–60 min) |
| Weekend holding | allowed in evaluation; not on funded Standard | secondary | research engine allows weekend holds; would need `close_before_weekend` for funded Standard |

## To verify (owner action)
1. Open https://ftmo.com/en/trading-objectives/ and the FTMO FAQ; compare each row above.
2. Edit the YAML, set `verified: true`, record URLs and the date in `sources`, bump `version`.
3. Re-run `tests/test_risk.py` and `scripts/ftmo_and_planning.py`.

## Simulation results (`research/ftmo_planning.json`, development split 2012–2017, 60 start dates, 120-day window)
| Stream | Risk/trade | Pass | 90 % CI | Breach |
|---|---|---|---|---|
| trend_pullback (best research candidate, after live portfolio limits) | 0.5 % | 6.7 % | 3–14 % | 8 % |
| trend_pullback | 1.0 % | 18 % | 12–28 % | 65 % |
| tsmom_weekly 120 d | 0.5 % | 0 % | 0–4 % | 0 % (all incomplete) |
| random baseline | 0.5 % | 0 % | 0–4 % | 45 % |
| hypothetical, zero edge, 1 trade/day | 1.0 % | 41 % | — | 51 % |
| hypothetical, +0.2 R/trade | 0.5 % | 45 % | — | 5 % |
| hypothetical, +0.2 R/trade | 1.0 % | 65 % | — | 24 % |

Reading: higher risk raises the pass rate *and* the breach rate, even with no edge — a pass is
weak evidence of skill. The intervals assume independent starts; overlapping windows make them
optimistic. The system never raises risk to chase the target.
