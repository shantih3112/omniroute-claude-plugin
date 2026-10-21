"""Deterministic position sizing.

The size is the LARGEST lot multiple whose loss at the stop (plus commission and an allowance
for spread/slippage) does not exceed the risk budget. It never rounds up: if even the broker's
minimum lot would risk more than the budget, the answer is "do not trade", not "trade the
minimum". Stops do not guarantee the fill price; gap risk is reported separately.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..instruments import Instrument


class ConversionError(ValueError):
    pass


def convert(amount: float, from_ccy: str, to_ccy: str, prices: dict[str, float]) -> float:
    """Convert using mid prices keyed like 'EURUSD'. Tries direct, inverse, then via USD."""
    if from_ccy == to_ccy:
        return amount
    d = prices.get(from_ccy + to_ccy)
    if d:
        return amount * d
    inv = prices.get(to_ccy + from_ccy)
    if inv:
        return amount / inv
    if "USD" not in (from_ccy, to_ccy):
        return convert(convert(amount, from_ccy, "USD", prices), "USD", to_ccy, prices)
    raise ConversionError(f"no price to convert {from_ccy}->{to_ccy}")


@dataclass
class SizeResult:
    ok: bool
    lots: float
    risk_amount: float          # account currency, at the stop incl. costs
    risk_pct: float
    loss_per_lot: float         # account currency
    margin: float               # account currency
    reason: str = ""
    gap_note: str = "A stop is not a guaranteed price; gaps and fast markets can fill worse."


def size_position(inst: Instrument, equity: float, account_ccy: str, risk_pct: float, entry: float, stop: float,
                  prices: dict[str, float], free_margin: float | None = None, spread_price: float = 0.0,
                  slippage_price: float = 0.0, leverage_margin_rate: float | None = None) -> SizeResult:
    if equity <= 0 or risk_pct <= 0:
        return SizeResult(False, 0.0, 0.0, 0.0, 0.0, 0.0, "equity and risk must be positive")
    dist = abs(entry - stop)
    if dist <= 0:
        return SizeResult(False, 0.0, 0.0, 0.0, 0.0, 0.0, "stop equals entry")
    budget = equity * risk_pct / 100.0
    # loss per 1.0 lot in QUOTE currency at the stop, including spread and slippage allowance
    loss_quote = (dist + spread_price + slippage_price) * inst.contract_size
    try:
        loss_acct = convert(loss_quote, inst.quote, account_ccy, prices)
        comm_acct = convert(2 * inst.commission_usd_per_lot_side, "USD", account_ccy, prices)
    except ConversionError as e:
        return SizeResult(False, 0.0, 0.0, 0.0, 0.0, 0.0, str(e))
    per_lot = loss_acct + comm_acct
    raw = budget / per_lot
    steps = math.floor(raw / inst.lot_step + 1e-9)
    lots = round(steps * inst.lot_step, 8)
    lots = min(lots, inst.max_lot)
    if lots < inst.min_lot:
        return SizeResult(False, 0.0, inst.min_lot * per_lot, 100 * inst.min_lot * per_lot / equity, per_lot, 0.0,
                          f"minimum lot {inst.min_lot} would risk {100 * inst.min_lot * per_lot / equity:.2f}% "
                          f"> budget {risk_pct:.2f}%: do not trade (never round up)")
    rate = leverage_margin_rate or inst.margin_rate
    try:
        notional_acct = convert(lots * inst.contract_size, inst.base, account_ccy, prices)
    except ConversionError as e:
        return SizeResult(False, 0.0, 0.0, 0.0, per_lot, 0.0, str(e))
    margin = notional_acct * rate
    if free_margin is not None and margin > free_margin:
        return SizeResult(False, lots, lots * per_lot, 100 * lots * per_lot / equity, per_lot, margin,
                          "insufficient free margin")
    return SizeResult(True, lots, lots * per_lot, 100 * lots * per_lot / equity, per_lot, margin)
