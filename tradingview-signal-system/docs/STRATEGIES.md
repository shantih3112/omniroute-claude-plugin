# Strategies: rules, rationale, failure modes

All rules are evaluated **only on closed bars**. "ATR" = ATR(14). R = distance from the signal close to the stop. Short rules mirror the long rules unless stated otherwise.

## Shared framework

- **Regime:** trend = UP / DOWN if ADX(14) ≥ 20 (stocks) or 22 (FX/crypto) and at least 4 of these 5 agree: close vs EMA200; EMA50 vs EMA200; EMA50 10-bar slope > 0.2 ATR; last two confirmed swing highs **and** lows rising (falling); DI+ vs DI−. RANGE = ADX < threshold − 2 and \|EMA50 slope\| < 0.5 ATR. Otherwise UNCERTAIN.
- **Swing pivots** use 5 bars on the left and 3 on the right. A pivot is only used **3 bars after** it formed, and zones start on the confirmation bar. Nothing is backdated.
- **HTF bias:** EMA20/EMA50 on the previous completed higher-timeframe bar. A long requires bias ≥ 0 (not DOWN); a short requires bias ≤ 0.
- **Execution plan:** limit at close ± 0.25 ATR, valid 3 bars. Stop clamped to ≥ 0.75 ATR (crypto 1.0); the setup is rejected above 3 ATR (crypto 3.5). T1 = 1R closes 50% and moves the stop to breakeven. T2 = 2R. 40-bar time stop. Exit on a trend flip against the trade or an opposite signal.
- **Priority** if several setups fire on one bar: D → A → B → C.
- **Global WAIT filters:** warm-up (250 bars), HTF not ready, ATR% above the 95th percentile, gap > 1.5 ATR, stock extended hours or session-open bar, ≤ 3 bars after earnings, FX rollover, manual blackouts, non-standard chart, unsupported type or timeframe.

## A · Trend pullback (ON by default)
- **Rationale:** trend persistence (time-series momentum) is among the better-documented price effects. Buying a shallow pullback inside an established trend improves the stop location compared with buying strength.
- **Long entry:** trend UP; within the last 3 bars the low came within EMA20 + 0.25 ATR; the bar closes above EMA20, closes bullish, and closes **above the prior bar's high** (resumption trigger); the close is ≤ 1 ATR above EMA20 (not extended).
- **Stop:** lowest low of the last 5 bars − 0.2 ATR. **Invalidation:** stop, or trend flips DOWN.
- **Suits:** clean trends on 4h/D. **Fails in:** late or exhausted trends, choppy high-ADX whipsaws, news shocks. On 1h data it lost money after costs.

## B · Squeeze breakout (ON by default)
- **Rationale:** volatility clusters. Low-volatility periods (narrow Bollinger width) tend to be followed by expansion, and a decisive close outside a range gives a clear, falsifiable trigger.
- **Long entry:** in the previous 5 bars, BB(20,2) width was in the lowest 20% of the last 120 bars. The bar closes above the prior 20-bar high, closes bullish, with range ≥ 1 ATR. Trend is not DOWN and HTF is not DOWN. For stocks/crypto with volume data, volume > 1.2 × its 20-bar average.
- **Stop:** midpoint of the prior 20-bar channel (clamped). **Invalidation:** stop (failed breakout), trend flips.
- **Suits:** consolidations before trend legs. **Fails in:** false breakouts, especially intraday and around scheduled news. This was the strongest component on the development data.

## C · Range mean reversion (OFF by default, experimental)
- **Rationale:** in non-trending regimes, closes beyond the bands tend to revert toward the mean.
- **Long entry:** trend = RANGE; the previous bar's low was below the lower BB and its RSI(14) < 35; this bar closes back inside the band, bullish. HTF is not DOWN.
- **Stop:** lowest low of 3 bars − 0.2 ATR. **Fails in:** range-to-trend transitions, where it catches falling knives.
- **Why off:** few trades and mixed signs on the development split (BTC 4h −0.79R over 7 trades).

## D · Liquidity-sweep reclaim (OFF by default, experimental)
- **Rationale:** an objective version of the "stop-run" idea from ICT-style teaching. Price trades through a confirmed swing low (where stops cluster) and closes back above it in the same bar.
- **Long entry:** the most recent **confirmed** swing low hasn't been swept yet; the bar's low goes below it and it closes above it, bullish, with a lower wick ≥ 50% of the range. Trend not DOWN, HTF not DOWN. Each level can be swept only once.
- **Stop:** bar low − 0.2 ATR.
- **Why off:** negative expectancy after costs on the development split in every market with trades (BTC 1h −0.57R over 51 trades, BTC 4h −0.39R, EURUSD 1h −0.38R).

## Baseline (for comparison only)
EMA20 crossing EMA50, with the same filters and the same exit framework. Selectable via *Signal logic* in both scripts.

## Researched but not implemented, and why
| Idea | Decision |
|---|---|
| Trendlines | Drawing them needs subjective anchor choice and is usually done in hindsight. The objective part (higher lows / lower highs) is already in the structure vote |
| Fibonacci retracements | No credible evidence that the 38.2/61.8 levels outperform arbitrary pullback depths; it adds parameters without a testable edge. The ATR/EMA pullback zone is simpler |
| Fair-value gaps / order blocks (ICT) | Definitions vary and are often marked after the fact. The one objectively definable ICT-like idea (the sweep) tested negative, so adding more is unjustified until it proves out |
| Opening-range / session breakouts | Need intraday session data per exchange. Our tests found sub-4h timeframes cost-sensitive. A candidate for a later version, with dedicated tests |
| Many-indicator agreement scores | Correlated indicators agreeing isn't independent confirmation. Deliberately avoided, and **no confidence/probability score is shown** because none has been validated |
