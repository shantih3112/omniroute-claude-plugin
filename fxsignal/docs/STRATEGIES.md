# Strategy specifications

Code: `src/fxsignal/strategies/library.py`. All rules are evaluated at the CLOSE of the signal
bar using completed bars only (truncation-invariance tests: `tests/test_no_lookahead.py`).
Common to all: market entry by the follower inside a two-sided zone (≤ +0.25 R worse, ≤ 0.5 R
better than the reference), signal expiry as listed, position size = risk engine's per-trade %
of equity divided by stop distance (never rounded up to the minimum lot), R measured against
the published stop. Evidence column refers to the development split (2012–2017), net of costs.

| Family | Edge rationale (claimed) | Data | Entry | Stop / exit | Expiry | Params searched | Unsuitable regimes / failure modes | Evidence |
|---|---|---|---|---|---|---|---|---|
| random (null) | none | H1 | random bar 08–17 London, random side | 1.5 ATR / 3 ATR / 48 h | 30 m | seed | – | −0.06…−0.12 R |
| ma_cross | trend persistence | H1 | EMA fast crosses slow | 2 ATR / 2R / 120 h | 60 m | 20/100, 50/200 | whipsaw in ranges | −0.05, −0.08 R |
| donchian_d1 (Turtle-like) | time-series momentum | D1 from H1 | D1 close beyond prior N-day channel | 2 ATR initial; trailing M-day opposite channel; 60 d | 4 h | 20/10, 55/20 | ranges, mean-reverting years | −0.07, −0.15 R |
| trend_pullback | buy dips in a D1 trend | H1 + D1 | D1 above rising EMA; H1 RSI dipped < x in 6 bars; close crosses back over EMA20; 08–17 London | below 10-bar low (0.8–3 ATR) / rr R / 72 h | 60 m | ema 50/100, rsi 35/40, rr 2/1.5 | trend exhaustion, news spikes | −0.03…−0.06 R |
| bb_reversion | range mean reversion | H1 | ADX < x; close re-enters Bollinger band | 3-bar extreme ± 0.5 ATR / middle band / 24 h | 60 m | adx 20/25, k 2/2.5 | trending breakouts | −0.14, −0.13 R (significantly negative) |
| squeeze_breakout | volatility clustering (compression→expansion) | H1 | ATR in bottom pct of 500 bars within 5 bars; close beyond 20-bar range | opposite side (0.8–3 ATR) / rr R / 48 h | 60 m | pct .2/.1, rr 2/1.5 | false breakouts | −0.02 R |
| asian_breakout | London-open order flow | M15 | first M15 close beyond 00–07 London range, 07–10 London | range mid or opposite / rr R / 16:00 London | 15 m | rr/stop mode | thin Asia ranges, news | −0.06, −0.04 R |
| sweep_reversal (ICT-style "liquidity sweep") | stop runs beyond prior-day extremes reverse | H1 + D1 | H1 trades beyond prior day high/low by ≥ x·ATR_D1 and closes back inside | sweep extreme + 0.1 ATR / rr R / 24 h | 60 m | pen .05/.1, rr 2/1.5 | real breakouts | −0.06, −0.05 R |
| tsmom_weekly | academic TSMOM | H1 + D1 | first Monday bar: sign of N-day return | 3 ATR_D1 / end of week | 4 h | 60/120 d | trend reversals | −0.01, −0.00 R |
| usd_fix | USD bid into 16:00 London fix, offered after (Krohn et al. 2024) | H1 | 14:00 long USD / 16:00 short USD | 1.5 ATR / time | 20 m | pre/post | — | −0.07, −0.04 R |
| round_break | stop clusters beyond round numbers (Osler 2003) | H1 | close through 100-pip level by 3 pips–0.5 ATR | 0.5 ATR beyond level / rr R / 24 h | 60 m | rr 1.5/1.0 | — | −0.10 R |

Not implemented as separate rules, with reasons:
* **Trendlines** – no objective, hindsight-free definition was found that is not equivalent to
  a channel/breakout rule already tested; hand-drawn lines are anchored on pivots only known later.
* **Fibonacci retracements** – need a swing high/low that is only confirmed after the fact;
  a causal version reduces to "pullback of x % of the last N-bar range", close to
  `trend_pullback`. No source with audited evidence was found.
* **ICT fair-value gaps, order blocks, "killzones"** – terms have several incompatible
  definitions; the testable core ("sweep then reverse inside session hours") is
  `sweep_reversal`, which failed. Session timing is covered by `asian_breakout`/`usd_fix`.
* **Carry / cross-sectional momentum** – need interest-rate data not available here.

Filters/ensembles: none was added because no base strategy had an edge to filter; adding
filters to a zero-edge rule mostly selects noise (the incremental-filter test in Gate V
would have required > 1 SE improvement on unseen data).

Confidence scores: none are published. No probability is shown anywhere, because nothing has
been calibrated on unseen data.
