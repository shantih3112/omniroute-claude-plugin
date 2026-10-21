# Research and experiment log

Every configuration ever run is also in `research/registry.jsonl` (append-only, with git commit,
data fingerprints and metrics). This log records the reasoning, including failures and bugs.

## Sources consulted (claims as stated by the source; status of OUR test in the tables below)

| Source | Claim (as stated by source) | Evidence type | Mechanism offered |
|---|---|---|---|
| Neely, Weller & Ulrich (2009), *JFQA* 44(2) 467–488 | Filter/MA rule profits in FX survived out-of-sample in the 1970s–80s but were gone by the early 1990s; less-studied rules declined too | Peer-reviewed, out-of-sample | Adaptive markets: edges are competed away |
| Moskowitz, Ooi & Pedersen (2012), *JFE* 104(2) | Time-series momentum across asset classes incl. FX futures, 1–12 month lookbacks | Peer-reviewed | Under-reaction then delayed over-reaction; hedging pressure |
| Ranaldo (2007), SNB Working Paper 2007-03, "Segmentation and time-of-day patterns in FX markets" | Domestic currencies depreciate during domestic working hours and appreciate during foreign hours | Working paper (SNB) | Home bias + market segmentation → dealer inventory pressure |
| Krohn, Mueller & Whelan (2024), *J. Finance* 79(1) 541–578 | USD appreciates before major FX fixes and depreciates after (W-shape over 24h), 9 currencies, 21 years | Peer-reviewed, replication package on Bank of Canada repository | Dealer inventory risk from unconditional dollar demand at fixes |
| Osler (2003), *J. Finance* (NY Fed SR 125) | Take-profit orders cluster at round numbers (reversals); stop-loss orders cluster just beyond them (faster trends after crossing) | Peer-reviewed, order-book data from one dealing bank | Order clustering |
| Bailey & López de Prado (2014), *J. Portfolio Management* — Deflated Sharpe Ratio | Selection among many trials inflates Sharpe; deflate by trial count | Methodology | — |
| Turtle rules (as described in C. Faith, *Way of the Turtle*, 2007) | 20/55-day channel breakouts with 2N stops | Book; historical results self-reported/anecdotal | Trend persistence |
| L. Connors & L. Raschke, *Street Smarts* (1995) — "Turtle Soup" | Failed breakouts of prior highs/lows reverse | Book; no audited record | Stop runs / trapped breakout traders |
| T. Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990) | Narrow-range/compression days precede expansion; opening-range breakouts | Book; no audited record | Volatility clustering / mean reversion of range |
| ICT (Inner Circle Trader) educational material — "liquidity sweeps", "fair value gaps", "killzones" | Price raids liquidity beyond prior highs/lows before reversing; session timing matters | Free videos/courses; **no audited performance record**; many terms lack fixed definitions | Stop-hunting by large participants (asserted) |

I did not watch videos for this work; ICT concepts are taken from widely circulated written
descriptions of the terms and were reduced to objective rules (see `sweep_reversal`). No
proprietary code was copied.

## Round 1 – pre-declared grids (GRIDS in `strategies/library.py`), development split

Run 2026-10-20, 11 FX pairs, base costs, entry one M15 bar after the signal, ±entry zone
(+0.25 R chase, −0.5 R drift). R measured against the signal's planned risk.

### Bugs found and fixed while running (results before the fixes are kept in the registry, tags `gateR`, `gateR-fix1`)
1. **pandas 3 timestamp units**: `asi8` returned microseconds in some indexes and nanoseconds in
   others; the first engine tests failed and caught it. All time arithmetic now normalises to ns.
2. **R measured at actual fill**: entries that drifted almost onto the stop produced −446 R
   "trades". R is now measured against planned risk, and fills that drifted > 0.5 R toward the
   stop are counted as missed (`missed_zone`).
3. **Vendor data holes**: EURCHF M15 has a 10-trading-day hole around the January 2015 SNB
   de-peg; a trade "held" through it showed +296 R. Trades spanning ≥ 2 h of missing market
   time are now excluded and counted (`data_gap`). The data audit also mis-classified long
   holes as weekends; fixed.

### Results (tag `gateR-fix2`) — Gate R requires exp ≥ +0.05 R, t ≥ 2, PF ≥ 1.10, n ≥ 200

| Family | Config | n | Net exp (R) | Gross exp (R) | t (weekly) | PF | Verdict |
|---|---|---|---|---|---|---|---|
| random (null) | 3 seeds | ~2,200 | −0.055 … −0.122 | −0.020 … −0.088 | −1.4 … −3.4 | 0.81–0.91 | reference |
| ma_cross | 20/100 | 3,645 | −0.049 | −0.017 | −1.8 | 0.93 | fail |
| ma_cross | 50/200 | 1,920 | −0.078 | −0.047 | −2.1 | 0.88 | fail |
| donchian_d1 | 20/10 | 462 | −0.070 | −0.027 | −0.9 | 0.86 | fail |
| donchian_d1 | 55/20 | 227 | −0.154 | −0.096 | −1.4 | 0.77 | fail |
| trend_pullback | ema50, rsi35, 2R | 1,132 | −0.026 | +0.001 | −0.6 | 0.95 | fail |
| trend_pullback | ema50, rsi40, 1.5R | 2,463 | −0.057 | −0.031 | −1.9 | 0.90 | fail |
| trend_pullback | ema100, rsi35, 2R | 1,205 | −0.031 | −0.003 | −0.8 | 0.94 | fail |
| bb_reversion | adx<20, 2σ | 944 | −0.140 | −0.097 | −3.6 | 0.76 | fail (significantly negative) |
| bb_reversion | adx<25, 2.5σ | 2,131 | −0.126 | −0.085 | −4.4 | 0.79 | fail (significantly negative) |
| squeeze_breakout | p20, 2R | 3,818 | −0.022 | +0.006 | −0.9 | 0.96 | fail |
| squeeze_breakout | p10, 1.5R | 2,781 | −0.024 | +0.002 | −1.0 | 0.96 | fail |
| asian_breakout | mid stop, 1.5R | 4,244 | −0.064 | −0.035 | −3.1 | 0.88 | fail |
| asian_breakout | opposite stop, 1R | 5,217 | −0.035 | −0.018 | −2.5 | 0.91 | fail |
| sweep_reversal (ICT-style) | pen 0.05, 2R | 4,454 | −0.064 | −0.028 | −3.3 | 0.89 | fail |
| sweep_reversal (ICT-style) | pen 0.10, 1.5R | 3,239 | −0.051 | −0.020 | −2.4 | 0.91 | fail |
| tsmom_weekly | 60d | 2,758 | −0.014 | −0.005 | −1.1 | 0.93 | fail |
| tsmom_weekly | 120d | 2,627 | −0.001 | +0.009 | −0.0 | 1.00 | fail |

**Reading:** none of the classic families has a gross edge distinguishable from zero on
2012–2017 majors/minors; after realistic costs all are negative. Mean-reversion at Bollinger
extremes and the London-open breakout are reliably *negative*, i.e. worse than random after
costs. This agrees with Neely, Weller & Ulrich (2009). Nothing from round 1 proceeds to validation.

## Round 2 – pre-declared before running (2026-10-20)

Three hypotheses with a published microstructure mechanism, one configuration each (plus the
stated alternative), development split only, same gates:

* **H2a `usd_prefix`** (Krohn et al. 2024): long USD from 14:00 to 16:00 London (the WM/R
  fix), USD pairs only. Stop 1.5 × H1 ATR, time exit at 16:00.
* **H2b `usd_postfix`** (Krohn et al. 2024; Ranaldo 2007 — USD weakens after European hours):
  short USD from 16:00 to 19:00 London. Stop 1.5 × H1 ATR, time exit.
* **H2c `round_break`** (Osler 2003): H1 close crosses a 100-pip round level by ≥ 3 pips and
  < 0.5 ATR, 07–18 London → continuation; stop 0.5 ATR back beyond the level; target 1.5 R;
  24 h time stop. Alternative declared in advance: target 1.0 R.

Additionally a descriptive (not traded) table of mean gross returns by London hour, to judge
whether intraday seasonality is large relative to the spread at all.

### Round 2 results (tag `gateR-r2`), development split, 11 FX pairs (USD pairs only for `usd_fix`)

| Hypothesis | n | Net exp (R) | Gross exp (R) | t | PF | Verdict |
|---|---|---|---|---|---|---|
| H2a `usd_fix` pre (long USD 14→16 London) | 5,849 | −0.073 | −0.050 | −4.6 | 0.79 | fail – sign opposite to hypothesis in this sample |
| H2b `usd_fix` post (short USD 16→19 London) | 6,696 | −0.035 | −0.012 | −2.3 | 0.87 | fail |
| H2c `round_break` 1.5 R | 3,581 | −0.102 | −0.067 | −4.9 | 0.83 | fail |
| H2c `round_break` 1.0 R (declared alternative) | 3,611 | −0.097 | −0.064 | −5.5 | 0.81 | fail |

Descriptive seasonality (`scripts/seasonality.py`): mean USD move per London hour is 0.1–0.6
pips, with signs that mostly flip between development and validation, against a ~1 pip
round-trip cost. Our 1-hour bars on 6 pairs therefore do not show a tradable version of the
published fix pattern; this neither confirms nor refutes the paper (which uses different
data, windows and test design).

### Engine bias check (tag `engine-bias-check`)
Random entries at zero cost and zero delay, 8 seeds: mean +0.017 R (sd 0.031 R between seeds).
The simulator is not producing the negative results by itself; the stop-first rule costs little.
The seed-to-seed sd (~0.03 R at ~2,200 trades) is a useful yardstick: gross effects of ±0.03 R
are indistinguishable from noise.

### XAUUSD, separate evaluation (tag `gateR-xau`)
All 17 configurations negative after costs (−0.035 to −1.1 R); the random null spans −0.06 to
−0.24 R. Small samples (15–450 trades) and 218 vendor holes in the M15 series. Fail.

## Conclusion after rounds 1–2 (2026-10-20)

**No tested strategy shows a credible edge.** 40 configurations across 13 families were
logged; none passes Gate R. The validation split and both holdouts remain **untouched** and
are kept for future, pre-declared hypotheses. Following SCORECARD §3, nothing is promoted to
the paper-forward feed. The live service is built and runs in *research-paper* mode: candidate
signals go only to the admin chat, labelled "RESEARCH – NO VALIDATED EDGE", to accumulate forward
evidence without anyone acting on them.

### What could still be tried (not done; each would need its own pre-declaration)
* Carry and cross-sectional currency momentum (Menkhoff et al. 2012) – need interest-rate
  history (not reachable from this environment).
* Event-driven rules around scheduled releases – need a historical calendar with actual/
  consensus values and release timestamps (not available here).
* Using measured broker spreads instead of the assumed table (costs are ~0.03 R/trade; they
  are not why the strategies fail — gross expectancy is already ≈ 0).

## Post-research studies (2026-10-20)

* **FTMO pass-rate study** (`scripts/ftmo_and_planning.py`, `research/ftmo_planning.json`):
  first version let all 11 pairs hold simultaneous positions; corrected to apply the live risk
  engine's portfolio limits (`backtest/portfolio.py`). Results in docs/FTMO.md.
* **Holdout disclosure**: the operational replay demo (`fxsignal replay --start 2026-09-14
  --days 12`, output `research/replay_demo_messages.txt`) ran research-status strategies on
  12 days of holdout B (4 signals). It tested plumbing, not performance; the outcomes were not
  used for any decision. Holdout B is therefore "untouched except for 12 days of plumbing replay".
* **Delay sensitivity** was not studied further: with no strategy passing Gate R there is no
  candidate whose manual-follow performance matters. The engine supports it
  (`run(..., source="dukascopy", delay_min=1|5|15|30)`).
