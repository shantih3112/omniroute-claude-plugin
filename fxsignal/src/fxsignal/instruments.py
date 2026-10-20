"""Instrument specifications and the cost assumptions attached to them.

All cost numbers are ASSUMPTIONS, not measurements from a broker. They are deliberately set
above commonly advertised raw-spread averages so that the research errs on the pessimistic
side. Replace them with measured values from the actual broker before trusting any result
(see docs/ASSUMPTIONS.md). Spreads are in pips; a pip is `pip_size` price units.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Instrument:
    symbol: str
    base: str
    quote: str
    pip_size: float
    digits: int
    contract_size: float = 100_000.0  # units of base currency per 1.0 lot
    min_lot: float = 0.01
    lot_step: float = 0.01
    max_lot: float = 50.0
    # Typical spread (pips) in liquid hours (London/NY overlap). ASSUMPTION.
    spread_pips: float = 0.5
    # Commission per 1.0 lot per side, in account-independent USD. ASSUMPTION.
    commission_usd_per_lot_side: float = 2.5
    # Approximate overnight financing cost per night (pips, charged regardless of
    # direction as a conservative stand-in for unknown swap sign). ASSUMPTION.
    swap_pips_per_night: float = 0.3
    margin_rate: float = 1 / 30  # 1:30 leverage assumption
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def currencies(self) -> tuple[str, str]:
        return (self.base, self.quote)


def _fx(sym: str, pip: float, digits: int, spread: float, **kw) -> Instrument:
    return Instrument(sym, sym[:3], sym[3:], pip, digits, spread_pips=spread, **kw)


INSTRUMENTS: dict[str, Instrument] = {
    i.symbol: i
    for i in [
        _fx("EURUSD", 0.0001, 5, 0.4, tags=("major",)),
        _fx("GBPUSD", 0.0001, 5, 0.7, tags=("major",)),
        _fx("USDJPY", 0.01, 3, 0.5, tags=("major",)),
        _fx("AUDUSD", 0.0001, 5, 0.5, tags=("major",)),
        _fx("USDCAD", 0.0001, 5, 0.7, tags=("major",)),
        _fx("USDCHF", 0.0001, 5, 0.7, tags=("major",)),
        _fx("EURGBP", 0.0001, 5, 0.8, tags=("minor",)),
        _fx("EURJPY", 0.01, 3, 0.9, tags=("minor",)),
        _fx("GBPJPY", 0.01, 3, 1.6, tags=("minor",)),
        _fx("AUDJPY", 0.01, 3, 1.0, tags=("minor",)),
        _fx("EURCHF", 0.0001, 5, 1.0, tags=("minor",)),
        # Gold: 1 lot = 100 oz; "pip" defined here as 0.01 USD. Spread 25 cents.
        Instrument("XAUUSD", "XAU", "USD", 0.01, 2, contract_size=100.0,
                   spread_pips=25.0, commission_usd_per_lot_side=2.5,
                   swap_pips_per_night=60.0, margin_rate=1 / 20, tags=("metal", "optional")),
    ]
}

FX_SYMBOLS = [s for s, i in INSTRUMENTS.items() if "metal" not in i.tags]


def get(symbol: str) -> Instrument:
    try:
        return INSTRUMENTS[symbol.upper()]
    except KeyError as e:
        raise KeyError(f"unknown instrument {symbol!r}") from e


def spread_multiplier(hour_utc: int) -> float:
    """Session-dependent spread multiplier (ASSUMPTION).

    Spreads widen sharply around the 17:00 New York rollover (21:00/22:00 UTC) and are wider
    in the Asian session for EUR/GBP/CHF crosses. One table is used for all pairs; it is coarse
    on purpose and is stress-tested at 2x in the research.
    """
    if hour_utc in (21, 22):
        return 4.0
    if hour_utc in (23, 0):
        return 2.0
    if 1 <= hour_utc <= 6:
        return 1.4
    return 1.0
