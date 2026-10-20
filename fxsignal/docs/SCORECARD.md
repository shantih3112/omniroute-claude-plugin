# Pre-registered quality scorecard (v1)

Written and committed **before any strategy backtest was run** (see git history). The thresholds
below may only be tightened. Loosening any of them requires a new scorecard version with a
written reason, and every strategy already evaluated must be re-scored under the new version,
with both results kept.

## 1. Data splits (fixed)

| Split | Period (UTC) | Data | Use |
|---|---|---|---|
| Development | 2012-11-16 → 2017-12-31 | ejtrader M15/H1, 11 FX pairs (+XAUUSD separately) | Idea testing, parameter choice |
| Validation | 2018-01-01 → 2020-12-31 | same | Walk-forward checks, filter ablations, selection. No parameter search here. |
| Holdout A | 2021-01-01 → 2022-03-04 | same | Used **once** for the final candidate set |
| Holdout B | 2022-03-07 → 2026-10-02 | Dukascopy M1 (EURUSD, GBPUSD, AUDUSD, USDCAD), OANDA M1 cross-check, OANDA M1 XAUUSD | Used **once**; also the manual-follow (human delay) test |

If a holdout is used more than once, this file and the research log must say so and it stops
being called "untouched".

## 2. Execution assumptions for every reported number

* Signals are computed only at completed-bar closes from data available at that time.
* Entry = first executable price **after** `signal close + processing latency + Telegram
  delivery + human reaction delay`. Default research delay: 1 bar of the execution series
  (M15 in dev/validation, 5 minutes in holdout B). Holdout B also reports 1, 5, 15 and 30 min.
* Longs buy at ask, sell at bid; shorts the reverse. Ask = bid + modelled spread
  (`instruments.py`, session multipliers). Commission charged both sides. Overnight financing
  charged as a cost every night held (sign unknown, so always a cost).
* Stop/target touched in the same execution bar → **stop first**. Gaps through a stop fill at
  the gapped price, not the stop.
* Entry not executable within the maximum entry deviation → counted as **missed**, reported.
* Base costs = instrument table; stress = 1.5× and 2× spread plus 0.3 pip extra slippage on stops.

## 3. Gates

### Gate R (research, development split; per strategy, pairs pooled)
1. ≥ 200 trades.
2. Net expectancy ≥ +0.05 R per trade at base costs and t-statistic ≥ 2.0 (trades clustered by
   week for the standard error).
3. Profit factor ≥ 1.10.

### Gate V (validation split; parameters frozen from development)
1. Net expectancy > 0 at base costs **and** > 0 at 1.5× costs.
2. Profit factor ≥ 1.05.
3. Positive net expectancy on ≥ 60 % of pairs with ≥ 20 trades.
4. Removing the best calendar year still leaves expectancy > 0.
5. Beats the **random-entry null** (same pairs, sessions, stop/target rules, trade count) at
   one-sided p < 0.05 by permutation.
6. A strategy more complex than the plain Donchian or MA baseline must beat that baseline's
   validation net expectancy per trade *and* its return / max drawdown at equal risk.
7. Each filter must improve validation expectancy by more than one standard error, or it is
   removed (ablation table required).

### Gate M (multiple testing)
Every configuration ever run is logged in `research/registry.jsonl`. For the selected candidate,
the Deflated Sharpe Ratio probability (Bailey & López de Prado, 2014), using the number of
logged trials in its family, must be ≥ 0.90 on development+validation combined.

### Gate H (holdouts, run once)
1. Net expectancy > 0 at base costs with a 5-minute delay (holdout B) and the default delay
   (holdout A).
2. Report the 90 % block-bootstrap confidence interval; a lower bound ≤ 0 means
   **"edge not established"** even if the point estimate is positive.
3. Portfolio max drawdown at 0.5 % risk per trade < 10 %.

### Promotion levels
* **Research only** – failed any of R/V/M.
* **Paper-forward candidate** – passed R, V, M. Published to the private Telegram feed, marked
  PAPER.
* **Holdout-confirmed** – also passed H.
* **Small-risk live consideration** – holdout-confirmed AND ≥ 3 months and ≥ 50 closed paper
  signals forward, with forward expectancy inside the backtest's 90 % interval and no
  unresolved operational incident. Never automatic; needs the owner's explicit decision.

## 4. Scorecard metrics reported for every candidate
Net expectancy (R and pips) · profit factor · win rate · average win / loss · max drawdown and
longest recovery (at 0.5 % risk) · worst trade, worst day, worst month · longest losing streak ·
trades per month · exposure (time in market) · by-pair / by-session / by-year / by-regime tables
· missed-entry rate · results at 1, 5, 15, 30 min delays · cost-stress results · bootstrap CI ·
comparison with random-entry and simple baselines.

## 5. Operational scorecard (live/paper service)
| Metric | Target |
|---|---|
| Bar close → Telegram API acceptance, p95 | ≤ 15 s |
| Daily report delivered | every calendar day |
| Duplicate signal messages | 0 |
| Signals published while data stale / calendar unknown | 0 |
| Unplanned downtime during market hours (forward test) | ≤ 1 % |
| Restart → full state recovery | automatic, verified by test |

## 6. Forward monitoring and pause rules (pre-set)
* **Investigate** when the forward drawdown exceeds the 90th percentile of the bootstrap
  drawdown distribution for the same number of trades, or when realised costs exceed
  modelled costs by > 50 % over 20 trades.
* **Pause new signals** at the 99th percentile, or on any data-integrity or duplicate-message
  incident. Pausing never deletes or hides existing signals.
* No retraining or rule changes because of a streak. Changes are versioned, re-run through
  gates R–M, and keep a rollback.

## 7. Trade-offs (stated, not optimised away)
* More selective filters → fewer signals, wider confidence intervals, slower evidence.
* Shorter timeframes → more signals but costs are a larger fraction of R and manual following
  is harder; M1–M5 strategies are presumed unsuitable for Telegram followers until shown otherwise.
* Wider stops → lower cost per R but larger position-size granularity problems on small accounts.
* "Daily opportunities" is a wish, not a target. Zero-signal days are expected and reported.
