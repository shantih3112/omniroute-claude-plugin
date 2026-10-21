# Multi-Market Signal Analyst (TradingView, Pine Script v6)

A current-chart analysis indicator that classifies the market (UP / DOWN / RANGE / UNCERTAIN), shows **BUY / SELL / WAIT** with explicit entry, stop-loss, targets, expiry and invalidation, and sends TradingView alerts. A matching strategy file runs the same confirmed logic in TradingView's Strategy Tester.

> **Status: written and checked offline. Not yet installed, compiled or tested in TradingView.**
> The build environment had no browser or computer control, and its network blocked tradingview.com. Nothing in this folder has been run inside your account. The installation steps below take about 10 minutes.

> **No proven edge.** Offline tests on real historical data (see [docs/BACKTESTING.md](docs/BACKTESTING.md)) gave mixed results with small samples, and clearly negative results on 1-hour crypto. Use this for analysis and paper trading only. It is not financial advice.

## Files

| File | Purpose |
|---|---|
| `build/indicator.pine` | **Paste this into TradingView** (indicator with dashboard, levels, alerts) |
| `build/strategy.pine` | **Paste this too** (backtest of the same logic) |
| `src/core.pine` | Shared logic. `build.py` assembles both scripts from it, so they cannot diverge |
| `backtest/` | Python port of the rules, offline backtest runner, results (`results.csv`, `table_*.md`) |
| `docs/STRATEGIES.md` | Rules, rationale, invalidation and failure modes of each setup, plus rejected ideas |
| `docs/BACKTESTING.md` | Method, costs, results by market/timeframe/split, and known gaps |

## Install (manual: about 10 minutes, desktop or web only)

1. Open TradingView in a browser or the desktop app and **create a new layout** (layout menu → *Create new layout*) so your existing work isn't touched. Name it `MM Analyst`.
2. Open **Pine Editor** → *Create new* → *Indicator*. Delete the template, paste the whole of `build/indicator.pine`, then **Save** as `Multi-Market Signal Analyst`.
3. Click **Add to chart**. If the compiler reports an error, copy the error line and send it to me. These scripts haven't been compiled by TradingView yet, so a first-run error is possible.
4. Repeat with `build/strategy.pine` (*Create new → Strategy*), saved as `Multi-Market Signal Analyst — Strategy`. Add it to a **separate** chart or pane when you want backtests; it isn't needed for alerts.
5. Use **standard candles**. The script refuses Heikin Ashi, Renko and other synthetic chart types.
6. Save the layout. Do **not** use *Publish script*: saving keeps it private.

## Reading the dashboard

| Row | Meaning |
|---|---|
| Market / Asset | Symbol, timeframe and detected profile (Stock / Forex / Crypto / Generic / Unsupported). Stocks are long-only by default. Crypto shows whether the symbol is spot or a perpetual |
| Trend | UP / DOWN need ADX ≥ threshold **and** ≥4 of 5 votes (price vs EMA200, EMA50 vs EMA200, EMA50 slope, swing structure HH/HL or LH/LL, DI+ vs DI−). RANGE = low ADX and a flat EMA50. Anything else is UNCERTAIN |
| HTF bias | EMA 20/50 position on the last **completed** higher-timeframe bar. Non-repainting |
| Volatility | ATR% percentile over 100 bars: LOW / NORMAL / HIGH / EXTREME |
| Setup | **BUY / SELL** only while a confirmed signal's entry window is open. Otherwise **WAIT** |
| Status | CONFIRMED (bar closed) · PRELIMINARY (live bar, may vanish, opt-in) · IN TRADE (late entry not advised) · INVALIDATED / CLOSED |
| Strategy / Levels | Which setup fired, when, the entry limit, SL, T1 and T2 |
| Why WAIT | Each active blocker (warm-up, extreme volatility, gap, extended hours, earnings, rollover, blackout, stop too wide…) or why no setup qualifies |
| Data | Missing volume, broker/exchange-specific prices, history length, timeframe caution, and **"News NOT checked"** |

**Trade plan conventions**
- **Entry:** limit order at signal close ± 0.25 ATR (no chasing). A pending entry expires after 3 bars.
- **Stop:** structural (swing/box), with a minimum of 0.75 ATR (1.0 for crypto). If the stop would need more than 3 ATR (3.5 for crypto), the setup is rejected.
- **Targets:** T1 at 1R closes half, then the stop moves to breakeven. T2 at 2R closes the rest.
- **Other exits:** a 40-bar time stop, a trend flip against the trade (**INVALIDATED**), or an opposite signal.
- **Stocks with shorting off:** a bearish setup shows **EXIT LONG**, never SELL.
- **Old signals on reload:** opening a chart never turns an old signal into a fresh BUY. Once the entry window has passed, the dashboard shows WAIT or IN TRADE.

## Alerts (TradingView app notifications)

Alerts run on TradingView's servers and keep working while you're offline, but **only for the exact symbol, timeframe, script version and inputs they were created with**. They don't follow whatever chart you open.

To create one per symbol/timeframe you want monitored:
1. Open that chart with the indicator applied → **Alert** (clock icon or Alt + A).
2. Condition: `Multi-Market Signal Analyst` → **`Any alert() function call`**. This delivers detailed messages for BUY, SELL, T1 hit, exits/invalidations and expiries, including symbol, timeframe, UTC timestamp, entry limit, SL, T1, T2 and cancel conditions.
   - Alternatively pick an individual condition (`1 · Confirmed BUY`, `2 · Confirmed SELL`, `3 · Exit / stop / invalidation`, `4 · Entry expired / cancelled`) with trigger **Once per bar close**.
3. Expiration: the longest your plan allows (or open-ended if your plan offers it).
4. Notifications: tick **Notify in app**. Optionally add *Show toast* and *Send email*. Leave the webhook off.
5. **Create**. Then check the *Alerts* panel to confirm it is listed as active.

**Warning alerts (information only, not trade signals).** These are included in the same "Any alert() function call" alert, or can be created separately as `5 · WARNING: volatility shock` / `6 · WARNING: trend change`:
- **Volatility shock ⚡**: a closed candle with a range ≥ 3 × ATR (adjustable; 5-bar cooldown). Often a news reaction.
- **Trend change**: the trend moves into or out of UP/DOWN and holds for 2 closed bars. RANGE ↔ UNCERTAIN changes aren't announced.
They never open, change or close a BUY/SELL signal. Turn them off under *6 · Warnings*.

On your phone:
- Install the TradingView app and log in to the same account.
- Allow notifications for TradingView in the phone's system settings (iOS: Settings → Notifications → TradingView; Android: Settings → Apps → TradingView → Notifications).
- Creating an alert doesn't prove notifications reach your phone. The first real alert, or a deliberately created test price alert, confirms delivery.

**Rules to remember**
- Historical chart markers are **not** alerts that were sent.
- Editing the script or changing inputs → **delete and recreate** the alerts, because alerts keep the version and settings they were created with.
- How many alerts you can have, and when they expire, depends on your plan. Check *Profile → Billing*, or the alert dialog's limits.
- One indicator does not scan all of TradingView. To monitor several instruments offline, create one alert per symbol/timeframe within your plan limit. Suggested starter set: a few liquid symbols on **4h or Daily**.

## Market and timeframe guidance

| Market | Notes |
|---|---|
| **Stocks** | Long-only by default. Signals are skipped on extended-hours bars, the first regular-session bar (intraday), gap bars, and the 3 bars after reported earnings. **Upcoming** earnings aren't used: check the "E" marker on the chart. Split/dividend adjustment follows your chart's *Adjust data* setting. Volume is exchange-specific. Free data may be delayed |
| **Forex** | No volume used (decentralized market). Quotes are broker-specific. Signals are skipped during the 16:45–17:45 New York rollover. Spreads widen around news: use the blackout inputs. Pairs sharing a currency (e.g. EURUSD + GBPUSD) are correlated exposure, which the script cannot see |
| **Crypto** | Trades 24/7. Prices and volume are exchange-specific: prefer a major spot exchange or the perpetual you actually trade. **Funding rates aren't modeled.** Shorting spot needs margin |
| **Generic** (indices, futures, CFDs, commodities) | Runs with stock-like defaults, but **not tested**. Treat as experimental |
| **Unsupported** (economic series, bonds, spreads…) | Always WAIT |

**Timeframes:** prefer **4h and Daily**. Tests below 4h were flat-to-negative after costs (BTC 1h clearly negative), and the dashboard says so. Seconds and tick charts are unsupported. Warm-up is 250 bars before any signal, and the HTF bias needs 50 higher-timeframe bars.

## What Pine Script can and cannot do (and how this script handles it)

| Capability | Status |
|---|---|
| OHLCV of the chart symbol and other symbols/timeframes (`request.security`) | ✅ used (HTF bias, no lookahead) |
| Reported earnings (`request.earnings`) | ✅ used: WAIT for N bars after a report (stocks) |
| Fundamentals (`request.financial`) and periodic economic series (`request.economic`) | Available, but values only: no schedule of upcoming releases, so they can't produce event warnings. Not used |
| Currency conversion (`request.currency_rate`) | ✅ used for the size estimate |
| News headlines, economic calendar, central-bank speeches, geopolitical events, hacks, regulation | ❌ **not accessible to Pine Script**. TradingView shows these in its UI (News, Calendar), but scripts can't read them. Substitute: manual event-blackout inputs (3 dated windows plus 1 daily window). The dashboard always says *News NOT checked* |
| External websites/APIs/webhooks *into* a script | ❌ not possible |
| Running while you are offline | ✅ only via server-side alerts you have created |
| Placing trades | Not done. The strategy is a backtest; it isn't connected to any broker |

## Known limitations and unverified items

- **Never compiled in TradingView yet.** It passed an offline Pine grammar parser, but type and semantic errors are only caught by TradingView's compiler.
- **Indicator vs. strategy:** both share identical decision code (verified by `diff`). The strategy's fills come from TradingView's broker emulator. On a bar that touches both stop and target, the emulator may resolve differently from the indicator's conservative *stop first* rule; a sync guard closes any resulting drift on the next bar.
- **Costs:** the strategy's commission and slippage are fixed per script (default 0.05% plus 2 ticks). Set *Properties* per market (see docs/BACKTESTING.md). Forex swaps and crypto funding aren't modeled.
- **Stop execution:** stops are chart levels, not orders. Gaps can fill beyond them. The script cannot enforce account-wide risk.
- **Size estimate** = risk ÷ (stop distance × point value × FX rate). It excludes costs, lot steps and minimum size. It's an estimate only.
- **No martingale, grid or loss-recovery sizing**, by design.
