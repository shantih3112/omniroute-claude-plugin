# Backtesting: method, results, limitations

## Why an offline backtest
TradingView's Strategy Tester could not be reached from the build environment, which had no browser and blocked tradingview.com. The confirmed-bar rules were therefore ported bar-for-bar to Python (`backtest/engine.py`) and run on **real public OHLC data**. This tests the *logic*, not TradingView's fills. Re-check every number in TradingView with `build/strategy.pine`.

Reproduce with: `python3 -I backtest/run.py <dir with the CSVs>`.

## Data (real, public, downloaded from GitHub raw files)
| Series | Source | Bars | Notes |
|---|---|---|---|
| GOOG daily 2004–2013 | `kernc/backtesting.py` test data | 2,148 | Unadjusted, pre-2014 split |
| AAPL daily 2015–2017 | `plotly/datasets` | 506 | Too short: only 2 trades after warm-up |
| EURUSD 1h 2017–2018 | `kernc/backtesting.py` test data | 5,000 | Timestamps assumed UTC; one broker feed |
| BTC/USD 1h 2011–2017 | `bukosabino/ta` test data (Bitstamp) | ~52k | Missing hours marked with a 1.7e308 sentinel → removed. 4h and D are resampled |

These are **dated and narrow** samples: one stock era, ten months of one FX pair, and BTC mostly in a historic bull market. They are not a substitute for testing your own instruments in TradingView.

## Method
- **Chronological splits per series:** first 60% of bars = development, next 20% = validation, last 20% = test. Indicators run causally over the full series. Each trade belongs to the split of its signal bar.
- **Parameters** were fixed before the first run (the Pine defaults) and **not optimised**. The only data-driven choice was turning strategies C and D off, decided from the **development split only**.
- **Execution:** the signal is generated at bar close; a limit entry is valid 3 bars; fills at open if price gaps through. Stop before target when both touch in one bar (conservative); gap-through stops fill at the open. T1 closes half and moves the stop to breakeven.
- **Costs per side** (commission + slippage + half spread): stocks 0.07%; EURUSD 0.007% (≈0.7 pip round trip incl. slippage); crypto 0.15%. A 2× cost stress test was also run. Swaps/funding are **not** modeled.
- **Sizing for equity/drawdown:** 1% risk per trade, capped at 1× notional (stocks/crypto) or 20× (FX). R figures are net of costs.

## Results: default configuration (A trend pullback + B squeeze breakout), net of costs
| Market | TF | Split | From | To | Trades | Win % | Avg win R | Avg loss R | Expectancy R | PF | Max DD % | Loss streak | Exposure % | Buy&hold % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GOOG | D | dev | 2004-08-19 | 2009-09-29 | 15 | 66.7 | 1.12 | -1.04 | 0.397 | 2.14 | 2.1 | 2.0 | 15.8 | 396.8 |
| GOOG | D | val | 2009-09-30 | 2011-06-14 | 2 | 50.0 | 1.18 | -1.04 | 0.07 | 1.14 | 1.0 | 1.0 | 2.8 | 2.5 |
| GOOG | D | test | 2011-06-15 | 2013-03-01 | 4 | 0.0 | 0.0 | -1.04 | -1.042 | 0.0 | 4.1 | 4.0 | 4.4 | 60.3 |
| AAPL | D | dev | 2015-02-17 | 2016-04-28 | 0 | – | – | – | – | – | – | – | 0.0 | -25.8 |
| AAPL | D | val | 2016-04-29 | 2016-09-21 | 1 | 0.0 | 0.0 | -1.06 | -1.056 | 0.0 | 1.1 | 1.0 | 3.0 | 21.1 |
| AAPL | D | test | 2016-09-22 | 2017-02-16 | 1 | 100.0 | 1.54 | 0.0 | 1.538 | inf | 0.0 | 0.0 | 32.4 | 18.1 |
| EURUSD | 1h | dev | 2017-04-19 | 2017-10-11 | 52 | 53.8 | 0.92 | -1.09 | -0.01 | 0.98 | 10.4 | 6.0 | 20.7 | 10.3 |
| EURUSD | 1h | val | 2017-10-11 | 2017-12-07 | 13 | 53.8 | 0.95 | -1.07 | 0.015 | 1.03 | 3.8 | 3.0 | 15.3 | -0.5 |
| EURUSD | 1h | test | 2017-12-08 | 2018-02-07 | 22 | 68.2 | 0.85 | -1.02 | 0.251 | 1.77 | 2.7 | 2.0 | 35.5 | 4.4 |
| EURUSD | 4h | dev | 2017-04-19 | 2017-10-11 | 9 | 66.7 | 0.97 | -1.02 | 0.305 | 1.89 | 2.0 | 2.0 | 13.7 | 10.3 |
| EURUSD | 4h | val | 2017-10-11 | 2017-12-07 | 4 | 25.0 | 0.43 | -1.03 | -0.664 | 0.14 | 2.6 | 2.0 | 24.4 | -0.5 |
| EURUSD | 4h | test | 2017-12-08 | 2018-02-07 | 7 | 57.1 | 1.21 | -1.03 | 0.251 | 1.57 | 2.1 | 2.0 | 32.8 | 4.4 |
| BTCUSD | 1h | dev | 2011-09-13 | 2015-07-13 | 518 | 51.4 | 0.93 | -1.22 | -0.115 | 0.81 | 32.6 | 9.0 | 25.9 | 4685.8 |
| BTCUSD | 1h | val | 2015-07-13 | 2016-08-02 | 166 | 44.6 | 0.9 | -1.21 | -0.267 | 0.6 | 33.2 | 11.0 | 26.4 | 108.8 |
| BTCUSD | 1h | test | 2016-08-02 | 2017-08-22 | 176 | 47.2 | 0.88 | -1.16 | -0.195 | 0.68 | 28.5 | 7.0 | 29.0 | 554.4 |
| BTCUSD | 4h | dev | 2011-09-13 | 2015-05-27 | 152 | 58.6 | 1.05 | -1.13 | 0.147 | 1.32 | 9.6 | 5.0 | 28.6 | 4077.5 |
| BTCUSD | 4h | val | 2015-05-27 | 2016-07-09 | 45 | 46.7 | 1.1 | -1.13 | -0.092 | 0.85 | 11.3 | 9.0 | 27.2 | 176.4 |
| BTCUSD | 4h | test | 2016-07-09 | 2017-08-22 | 50 | 66.0 | 1.09 | -1.0 | 0.378 | 2.11 | 3.2 | 3.0 | 30.9 | 498.6 |
| BTCUSD | D | dev | 2011-09-13 | 2015-04-15 | 18 | 77.8 | 1.04 | -0.95 | 0.596 | 3.84 | 1.6 | 1.0 | 27.0 | 3633.3 |
| BTCUSD | D | val | 2015-04-16 | 2016-06-18 | 9 | 66.7 | 0.95 | -1.07 | 0.277 | 1.78 | 1.1 | 1.0 | 41.6 | 231.8 |
| BTCUSD | D | test | 2016-06-19 | 2017-08-22 | 10 | 80.0 | 1.29 | -1.01 | 0.831 | 5.1 | 1.0 | 1.0 | 24.2 | 416.7 |

### Simple baseline (EMA20/50 cross, same filters and exits)
| Market | TF | Split | From | To | Trades | Win % | Avg win R | Avg loss R | Expectancy R | PF | Max DD % | Loss streak | Exposure % | Buy&hold % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GOOG | D | dev | 2004-08-19 | 2009-09-29 | 7 | 100.0 | 1.06 | 0.0 | 1.064 | inf | 0.0 | 0.0 | 6.3 | 396.8 |
| GOOG | D | val | 2009-09-30 | 2011-06-14 | 2 | 0.0 | 0.0 | -1.06 | -1.064 | 0.0 | 2.1 | 2.0 | 1.9 | 2.5 |
| GOOG | D | test | 2011-06-15 | 2013-03-01 | 3 | 66.7 | 0.75 | -1.04 | 0.156 | 1.45 | 1.0 | 1.0 | 5.8 | 60.3 |
| AAPL | D | dev | 2015-02-17 | 2016-04-28 | 1 | 100.0 | 0.38 | 0.0 | 0.376 | inf | 0.0 | 0.0 | 7.3 | -25.8 |
| AAPL | D | val | 2016-04-29 | 2016-09-21 | 1 | 0.0 | 0.0 | -1.23 | -1.23 | 0.0 | 0.7 | 1.0 | 1.0 | 21.1 |
| AAPL | D | test | 2016-09-22 | 2017-02-16 | 1 | 100.0 | 1.22 | 0.0 | 1.225 | inf | 0.0 | 0.0 | 29.4 | 18.1 |
| EURUSD | 1h | dev | 2017-04-19 | 2017-10-11 | 31 | 41.9 | 0.92 | -1.07 | -0.235 | 0.62 | 11.8 | 5.0 | 12.7 | 10.3 |
| EURUSD | 1h | val | 2017-10-11 | 2017-12-07 | 7 | 85.7 | 0.92 | -1.07 | 0.638 | 5.19 | 1.1 | 1.0 | 8.3 | -0.5 |
| EURUSD | 1h | test | 2017-12-08 | 2018-02-07 | 16 | 31.2 | 0.74 | -1.02 | -0.471 | 0.33 | 7.7 | 5.0 | 14.3 | 4.4 |
| EURUSD | 4h | dev | 2017-04-19 | 2017-10-11 | 8 | 50.0 | 0.94 | -1.03 | -0.044 | 0.91 | 2.2 | 2.0 | 9.7 | 10.3 |
| EURUSD | 4h | val | 2017-10-11 | 2017-12-07 | 6 | 50.0 | 1.46 | -1.03 | 0.215 | 1.42 | 3.1 | 3.0 | 18.2 | -0.5 |
| EURUSD | 4h | test | 2017-12-08 | 2018-02-07 | 2 | 100.0 | 0.93 | 0.0 | 0.925 | inf | 0.0 | 0.0 | 23.2 | 4.4 |
| BTCUSD | 1h | dev | 2011-09-13 | 2015-07-13 | 384 | 42.7 | 1.05 | -1.04 | -0.148 | 0.75 | 44.4 | 8.0 | 21.3 | 4685.8 |
| BTCUSD | 1h | val | 2015-07-13 | 2016-08-02 | 155 | 36.1 | 0.91 | -1.05 | -0.341 | 0.49 | 38.6 | 11.0 | 23.6 | 108.8 |
| BTCUSD | 1h | test | 2016-08-02 | 2017-08-22 | 133 | 46.6 | 0.79 | -1.21 | -0.281 | 0.57 | 23.1 | 7.0 | 22.3 | 554.4 |
| BTCUSD | 4h | dev | 2011-09-13 | 2015-05-27 | 90 | 56.7 | 0.92 | -1.01 | 0.082 | 1.19 | 10.1 | 4.0 | 20.1 | 4077.5 |
| BTCUSD | 4h | val | 2015-05-27 | 2016-07-09 | 35 | 40.0 | 0.93 | -1.05 | -0.259 | 0.59 | 10.3 | 7.0 | 19.6 | 176.4 |
| BTCUSD | 4h | test | 2016-07-09 | 2017-08-22 | 26 | 42.3 | 1.0 | -1.01 | -0.162 | 0.72 | 5.4 | 4.0 | 14.9 | 498.6 |
| BTCUSD | D | dev | 2011-09-13 | 2015-04-15 | 8 | 87.5 | 1.05 | -0.94 | 0.799 | 7.83 | 0.9 | 1.0 | 8.1 | 3633.3 |
| BTCUSD | D | val | 2015-04-16 | 2016-06-18 | 4 | 50.0 | 1.4 | -0.95 | 0.222 | 1.46 | 1.9 | 2.0 | 14.9 | 231.8 |
| BTCUSD | D | test | 2016-06-19 | 2017-08-22 | 4 | 50.0 | 1.56 | -0.79 | 0.387 | 1.98 | 1.0 | 1.0 | 23.3 | 416.7 |

### 2× cost stress test (default configuration)
| Market | TF | Split | From | To | Trades | Win % | Avg win R | Avg loss R | Expectancy R | PF | Max DD % | Loss streak | Exposure % | Buy&hold % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GOOG | D | dev | 2004-08-19 | 2009-09-29 | 15 | 66.7 | 1.09 | -1.08 | 0.364 | 2.01 | 2.2 | 2.0 | 15.8 | 396.8 |
| GOOG | D | val | 2009-09-30 | 2011-06-14 | 2 | 50.0 | 1.12 | -1.08 | 0.022 | 1.04 | 1.1 | 1.0 | 2.8 | 2.5 |
| GOOG | D | test | 2011-06-15 | 2013-03-01 | 4 | 0.0 | 0.0 | -1.08 | -1.085 | 0.0 | 4.3 | 4.0 | 4.4 | 60.3 |
| AAPL | D | dev | 2015-02-17 | 2016-04-28 | 0 | – | – | – | – | – | – | – | 0.0 | -25.8 |
| AAPL | D | val | 2016-04-29 | 2016-09-21 | 1 | 0.0 | 0.0 | -1.11 | -1.112 | 0.0 | 1.1 | 1.0 | 3.0 | 21.1 |
| AAPL | D | test | 2016-09-22 | 2017-02-16 | 1 | 100.0 | 1.51 | 0.0 | 1.507 | inf | 0.0 | 0.0 | 32.4 | 18.1 |
| EURUSD | 1h | dev | 2017-04-19 | 2017-10-11 | 52 | 53.8 | 0.85 | -1.17 | -0.083 | 0.85 | 12.1 | 6.0 | 20.7 | 10.3 |
| EURUSD | 1h | val | 2017-10-11 | 2017-12-07 | 13 | 53.8 | 0.88 | -1.15 | -0.056 | 0.89 | 4.2 | 3.0 | 15.3 | -0.5 |
| EURUSD | 1h | test | 2017-12-08 | 2018-02-07 | 22 | 68.2 | 0.78 | -1.09 | 0.189 | 1.55 | 2.9 | 2.0 | 35.5 | 4.4 |
| EURUSD | 4h | dev | 2017-04-19 | 2017-10-11 | 9 | 66.7 | 0.94 | -1.05 | 0.278 | 1.79 | 2.1 | 2.0 | 13.7 | 10.3 |
| EURUSD | 4h | val | 2017-10-11 | 2017-12-07 | 4 | 25.0 | 0.37 | -1.06 | -0.701 | 0.12 | 2.8 | 2.0 | 24.4 | -0.5 |
| EURUSD | 4h | test | 2017-12-08 | 2018-02-07 | 7 | 57.1 | 1.17 | -1.06 | 0.216 | 1.48 | 2.1 | 2.0 | 32.8 | 4.4 |
| BTCUSD | 1h | dev | 2011-09-13 | 2015-07-13 | 518 | 46.7 | 0.81 | -1.39 | -0.364 | 0.51 | 73.8 | 10.0 | 25.9 | 4685.8 |
| BTCUSD | 1h | val | 2015-07-13 | 2016-08-02 | 166 | 34.3 | 0.85 | -1.31 | -0.567 | 0.34 | 53.4 | 14.0 | 26.4 | 108.8 |
| BTCUSD | 1h | test | 2016-08-02 | 2017-08-22 | 176 | 39.2 | 0.8 | -1.34 | -0.497 | 0.39 | 46.4 | 10.0 | 29.0 | 554.4 |
| BTCUSD | 4h | dev | 2011-09-13 | 2015-05-27 | 152 | 57.9 | 0.96 | -1.29 | 0.017 | 1.03 | 11.7 | 5.0 | 28.6 | 4077.5 |
| BTCUSD | 4h | val | 2015-05-27 | 2016-07-09 | 45 | 46.7 | 0.95 | -1.3 | -0.248 | 0.64 | 13.9 | 9.0 | 27.2 | 176.4 |
| BTCUSD | 4h | test | 2016-07-09 | 2017-08-22 | 50 | 66.0 | 0.97 | -1.1 | 0.269 | 1.72 | 3.4 | 3.0 | 30.9 | 498.6 |
| BTCUSD | D | dev | 2011-09-13 | 2015-04-15 | 18 | 77.8 | 1.0 | -0.97 | 0.563 | 3.61 | 1.7 | 1.0 | 27.0 | 3633.3 |
| BTCUSD | D | val | 2015-04-16 | 2016-06-18 | 9 | 66.7 | 0.9 | -1.14 | 0.221 | 1.58 | 1.2 | 1.0 | 41.6 | 231.8 |
| BTCUSD | D | test | 2016-06-19 | 2017-08-22 | 10 | 80.0 | 1.22 | -1.02 | 0.774 | 4.78 | 1.0 | 1.0 | 24.2 | 416.7 |

### By strategy (trades / expectancy in R, net)
| Market | TF | Strategy | Dev trades / exp R | Val | Test |
|---|---|---|---|---|---|
| AAPL | D | BO | 0 / – | 0 / – | 1 / 1.54 |
| AAPL | D | MR | 0 / – | 0 / – | 0 / – |
| AAPL | D | SW | 0 / – | 0 / – | 0 / – |
| AAPL | D | TP | 0 / – | 1 / -1.06 | 0 / – |
| BTCUSD | 1h | BO | 293 / -0.01 | 85 / -0.16 | 97 / -0.14 |
| BTCUSD | 1h | MR | 25 / 0.24 | 9 / -0.51 | 5 / -0.71 |
| BTCUSD | 1h | SW | 51 / -0.57 | 23 / -0.47 | 23 / -0.45 |
| BTCUSD | 1h | TP | 280 / -0.15 | 99 / -0.39 | 101 / -0.32 |
| BTCUSD | 4h | BO | 76 / 0.35 | 25 / -0.01 | 30 / 0.54 |
| BTCUSD | 4h | MR | 7 / -0.79 | 1 / -1.26 | 0 / – |
| BTCUSD | 4h | SW | 15 / -0.39 | 4 / -0.44 | 3 / -0.85 |
| BTCUSD | 4h | TP | 95 / 0.10 | 23 / -0.10 | 26 / 0.27 |
| BTCUSD | D | BO | 12 / 0.86 | 5 / 0.24 | 4 / 1.16 |
| BTCUSD | D | MR | 0 / – | 0 / – | 0 / – |
| BTCUSD | D | SW | 2 / 0.46 | 1 / -1.11 | 1 / 1.42 |
| BTCUSD | D | TP | 7 / -0.09 | 5 / 0.36 | 6 / 0.61 |
| EURUSD | 1h | BO | 35 / 0.08 | 9 / 0.50 | 15 / 0.41 |
| EURUSD | 1h | MR | 1 / 0.45 | 3 / -0.22 | 2 / -1.09 |
| EURUSD | 1h | SW | 6 / -0.38 | 3 / 0.23 | 1 / 1.39 |
| EURUSD | 1h | TP | 23 / -0.23 | 4 / -1.08 | 11 / -0.26 |
| EURUSD | 4h | BO | 6 / 0.47 | 3 / -1.03 | 4 / 0.21 |
| EURUSD | 4h | MR | 1 / 1.41 | 1 / 0.47 | 0 / – |
| EURUSD | 4h | SW | 2 / -0.29 | 1 / -1.04 | 0 / – |
| EURUSD | 4h | TP | 5 / 0.57 | 1 / 0.43 | 3 / 0.31 |
| GOOG | D | BO | 6 / 0.78 | 1 / 1.18 | 3 / -1.03 |
| GOOG | D | MR | 0 / – | 0 / – | 0 / – |
| GOOG | D | SW | 1 / -1.07 | 0 / – | 0 / – |
| GOOG | D | TP | 11 / 0.31 | 1 / -1.04 | 1 / -1.07 |

Sample counts include long and short trades; stocks were long-only.

## Interpretation
- **No robust edge has been demonstrated.** Only BTC daily was positive in all three splits, with just 18/9/10 trades during an extraordinary bull market. There it far underperformed buy-and-hold, so a long-biased system looking good is unsurprising.
- **BTC 1h loses in every split** (−0.12R / −0.27R / −0.20R per trade) and collapses at 2× costs. Intraday crypto with these rules is not viable. The dashboard warns below 4h.
- **BTC 4h:** +0.15R dev, −0.09R validation, +0.38R test. The sign changes, so it's unproven.
- **EURUSD 1h:** about zero on dev and validation, +0.25R on test (22 trades). Inconclusive.
- **Stocks (GOOG, AAPL):** too few trades (2–15 per split) for any conclusion; GOOG's test split was 4 losses out of 4.
- **Versus baseline:** the full system lost less than the baseline on BTC 1h/4h and EURUSD 1h, but not on GOOG dev or BTC D. The extra complexity isn't clearly justified on unseen data.
- Win rates of 45–80% come from the 1R partial target, not from predictive accuracy. **No probability or confidence score is shown anywhere**, because none has been validated.

## What the TradingView Strategy Tester will and won't reproduce
- It uses the same decision code as the indicator (identical core, verified by `diff`).
- Its emulator assumes an intrabar path (open → nearer extreme → other extreme), which differs from the "stop first" rule here. *Bar Magnifier* (premium plans) improves this.
- Commission and slippage are single values per script. Set them in **Properties** per market:

| Market | Commission | Slippage (ticks) | Comment |
|---|---|---|---|
| US stocks | 0.05% (or your broker's fee) | 1–2 | Add more for small caps |
| Major FX | 0 | ≈ the spread in ticks (e.g. 10 ticks = 1 pip on 5-digit quotes) | Swap not modeled |
| Crypto spot | 0.1% | 2+ | Perpetuals: funding not modeled |

- **Never** evaluate fills on Heikin Ashi/Renko charts (the script refuses them).
- Results depend on how much history your plan loads.
- Report every symbol and timeframe you test, not just the good ones.

## Differences: Python port vs. Pine
Pivot tie handling may differ slightly. The port has no earnings filter, extended-hours or session-open filter, or manual blackouts (there was no such data). Volume filters used the dataset's volume. Exact numbers will differ from TradingView's; the direction of the conclusions is what this test supports.
