# Data: sources, provenance, validation

No broker or paid vendor feed was available in the build environment (most market-data hosts
were blocked by its network policy). Research uses public mirrors on GitHub, cross-checked
against each other. All are **BID-only**; the ask is modelled from the spread table in
`instruments.py`. "Tick volume" is a count of price updates at one vendor, **not traded volume**;
spot FX has no central order book or consolidated volume.

| Name | Mirror (commit pinned in `data/raw/*/SOURCE_COMMIT`) | Content | Clock | Use |
|---|---|---|---|---|
| ejtrader | github.com/ejtraderLabs/historical-data (identical to komo135/forex-historical-data) | MT5 export, 11 FX + XAUUSD, M15/M30/H1, 2012-11 → 2022-03-04, fixed 230,400 M15 rows | EET/EEST, **EU** DST (verified) | Development, validation, holdout A |
| Dukascopy | github.com/pyronmitchell9713-hue/EURGBP (GitHub Actions download from Dukascopy) | M1 BID, EURUSD/GBPUSD/AUDUSD/USDCAD, 2020-01 → 2026-10-04 | UTC | Holdout B, replay |
| OANDA | same repo, `data/raw/oanda` | M1 BID, same 4 pairs + XAUUSD (2019→), → 2026-10-08 | UTC | Cross-check, XAUUSD |
| HistData | github.com/asiertrades/HISDATA-EURUSD | EURUSD M1 2000–2025 | inconsistent (see below) | Cross-check only |

Provenance caveat: these are third-party mirrors, not vendor-signed files. Their mutual
agreement (below) is strong evidence they are genuine, but not proof of completeness.

## Cross-vendor agreement (H1 closes, `research/data_audit.json`)
| Pair | ejtrader vs Dukascopy | Dukascopy vs OANDA |
|---|---|---|
| EURUSD | median 0.1 pip, p99 1.7 | median 0.6, p99 2.4 |
| GBPUSD | 0.2 / 3.4 | 0.5 / 3.7 |
| AUDUSD | 0.2 / 2.0 | 0.2 / 2.3 |
| USDCAD | 0.2 / 3.0 | 0.3 / 3.1 |
Shifting either series by ±1 h raises the median difference to 4–7 pips, which pins the
timezone conversion. XAUUSD ejtrader vs OANDA: median 7 cents, p99 1.55 USD (different LPs).

## Problems found and how they are handled
1. **ejtrader clock is EU-DST, not New-York-aligned**: first assumption (NY+7) was wrong during
   the 2–3 weeks a year when US and EU DST differ (p99 error 20–34 pips). Fixed; its own H4/D1
   files are not used (H4/D1 are rebuilt from H1 on New York 17:00 boundaries).
2. **HistData mirror**: matches Dukascopy only when read as New York local time with DST in
   2015–2025, but is off by an hour in 2012–2014 and in US/EU DST-mismatch weeks. Demoted to
   cross-check only.
3. **Vendor holes**: EURCHF has a 10-trading-day hole around the January 2015 SNB de-peg,
   USDCHF ~28 h, GBPJPY ~14 h, XAUUSD 218 holes (M15). Trades spanning a hole of ≥ 2 h of
   market time are excluded and counted (`data_gap`) rather than given an invented outcome.
4. **pandas 3 timestamp resolution** (µs vs ns) silently broke time arithmetic until tests caught it.

## Live data rules
* Only completed M1 bars are used (OANDA `complete: true`). The live gate rejects out-of-order,
  duplicate, inconsistent bars, flags > 25 robust-σ jumps, and marks a symbol `stale` when the
  newest bar is > 180 s old during market hours. Any non-`ok` status blocks new signals for that symbol.
* Market hours: Sunday 17:00 → Friday 17:00 New York. Dec 24–26, Dec 31–Jan 2 are treated as
  illiquid (no new signals).
* Internally everything is UTC; messages show Europe/Oslo time with the zone abbreviation.

## Reproduce
```bash
.venv/bin/python scripts/data_audit.py      # quality + cross-vendor tables
```
(fetch the mirrors into `data/raw/` first; paths in `src/fxsignal/data/loaders.py`).
