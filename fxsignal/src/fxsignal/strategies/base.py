"""Strategy interface.

A strategy is a pure function of completed bars. `generate()` receives bars for the signal
timeframe (and context timeframes built from the same data) and returns one row per signal:

  time        decision time = CLOSE time of the signal bar (UTC). Nothing after it was used.
  side        +1 long / -1 short
  entry_type  "market" (act on next price) or "limit" (rest an order at entry_ref)
  entry_ref   reference price: bid close for market signals, the limit level for limit signals
  stop        protective stop price (absolute)
  target      take-profit price (absolute) or NaN
  max_hold_min  time stop in minutes from entry
  expiry_min  how long the signal stays actionable for a follower
  atr         ATR of the signal timeframe at decision time (price units)
  regime      causal regime label at decision time
  note        short human-readable rationale

The same code runs in research (whole history at once) and live (rolling window); the
truncation-invariance tests prove both give identical rows for the same decision time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..data.resample import resample, tf_delta

SIGNAL_COLUMNS = ["time", "side", "entry_type", "entry_ref", "stop", "target", "max_hold_min",
                  "expiry_min", "atr", "regime", "note"]


@dataclass
class Strategy:
    name: str = "base"
    version: str = "1"
    signal_tf: str = "H1"
    context_tfs: tuple[str, ...] = ("D1",)
    params: dict = field(default_factory=dict)
    warmup_bars: int = 400
    # trailing stop levels, filled by generate() when the strategy uses them:
    # DataFrame indexed by availability time with columns long_trail / short_trail
    trail: pd.DataFrame | None = None

    @property
    def id(self) -> str:
        p = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.name}@{self.version}[{p}]"

    def bars(self, sig: pd.DataFrame) -> dict[str, pd.DataFrame]:
        out = {self.signal_tf: sig}
        for tf in self.context_tfs:
            out[tf] = resample(sig, tf)
        return out

    def generate(self, sig: pd.DataFrame) -> pd.DataFrame:  # pragma: no cover - interface
        raise NotImplementedError

    # helpers -----------------------------------------------------------------------------
    def frame(self, df: pd.DataFrame, mask: pd.Series, side: np.ndarray | int, tf: str | None = None,
              **cols) -> pd.DataFrame:
        """Rows for bars where `mask` is true; `tf` is the timeframe of `df` (default signal_tf)."""
        idx = df.index[mask.fillna(False).to_numpy(bool)]
        out = pd.DataFrame(index=idx)
        out["time"] = idx + tf_delta(tf or self.signal_tf)
        out["side"] = side if np.isscalar(side) else np.asarray(side)[mask.fillna(False).to_numpy(bool)]
        for k, v in cols.items():
            if isinstance(v, pd.Series):
                out[k] = v.reindex(idx).to_numpy()
            else:
                out[k] = v
        for c in SIGNAL_COLUMNS:
            if c not in out:
                out[c] = np.nan if c not in ("entry_type", "regime", "note") else ""
        return out[SIGNAL_COLUMNS].reset_index(drop=True)


def concat_signals(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if len(f)]
    if not frames:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)
    return pd.concat(frames, ignore_index=True).sort_values("time", kind="stable").reset_index(drop=True)
