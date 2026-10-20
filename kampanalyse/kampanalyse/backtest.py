"""Historisk modelltest – tidsbasert og uten lekkasje.

Datakilde: CSV i football-data.co.uk-format (kolonner Date, HomeTeam, AwayTeam, FTHG, FTAG
og odds som PSH/PSD/PSA, PSCH/PSCD/PSCA, AvgH/AvgD/AvgA, MaxH/MaxD/MaxA, B365H/...).

Metode:
- For hver kampdag brukes kun kamper FØR datoen til å estimere lagstyrke (refit ukentlig;
  modellen tilpasses aldri på data etter tilpasningsdatoen).
- Markedsreferanse: marginfrie åpningsodds (Pinnacle hvis finnes, ellers snitt).
- Modell, markedsreferanse og blanding sammenlignes med log loss og Brier.
- Kalibrering: 10 sannsynlighetsintervaller, observert treff vs snitt-estimat.
- Spill-simulering: flat 1 enhet når konservativ EV ≥ terskel, mot en tilgjengelig pris
  (B365 eller snitt – IKKE maks-odds, som er urealistisk å få). CLV mot Pinnacle sluttodds.
"""
from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .markets import Result, Selection
from .model import fit, result_distribution
from .probability import devig_power
from .providers.base import HistMatch


@dataclass
class Row:
    d: date
    home: str
    away: str
    hg: int
    ag: int
    open_odds: tuple[float, float, float] | None
    bet_odds: tuple[float, float, float] | None
    close_odds: tuple[float, float, float] | None


def _f(r: dict, *keys) -> tuple[float, float, float] | None:
    for k in keys:
        try:
            v = (float(r[k + "H"]), float(r[k + "D"]), float(r[k + "A"]))
            if all(x > 1 for x in v):
                return v
        except (KeyError, ValueError, TypeError):
            continue
    return None


def _date(s: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(s)


def load_csv(path: str) -> list[Row]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            try:
                out.append(Row(_date(r["Date"]), r["HomeTeam"], r["AwayTeam"], int(r["FTHG"]), int(r["FTAG"]),
                               _f(r, "PS", "Avg", "B365"), _f(r, "B365", "Avg"), _f(r, "PSC", "AvgC")))
            except (KeyError, ValueError):
                continue
    return sorted(out, key=lambda x: x.d)


@dataclass
class Report:
    n: int = 0
    ll: dict = field(default_factory=lambda: {"marked": 0.0, "modell": 0.0, "blanding": 0.0})
    brier: dict = field(default_factory=lambda: {"marked": 0.0, "modell": 0.0, "blanding": 0.0})
    calib: list = field(default_factory=lambda: [[0, 0.0, 0] for _ in range(10)])  # n, sum p, treff
    bets: int = 0
    staked: float = 0.0
    returned: float = 0.0
    clv: list = field(default_factory=list)
    first: date | None = None
    last: date | None = None

    def text(self) -> str:
        if not self.n:
            return "Ingen kamper evaluert (for lite data etter oppvarmingsperioden)."
        lines = [f"Testperiode: {self.first} – {self.last}, {self.n} kamper (H/U/B).", "",
                 "Gjennomsnittlig log loss (lavere er bedre):"]
        for k in ("marked", "modell", "blanding"):
            lines.append(f"  {k:9s} {self.ll[k] / self.n:.4f}   Brier {self.brier[k] / self.n:.4f}")
        lines.append("")
        lines.append("Kalibrering (blanding): intervall · antall · snitt estimat · observert")
        for i, (n, sp, hit) in enumerate(self.calib):
            if n:
                lines.append(f"  {i * 10:>2}–{i * 10 + 10:<3}% · {n:5d} · {sp / n:6.1%} · {hit / n:6.1%}")
        lines.append("")
        if self.bets:
            roi = (self.returned - self.staked) / self.staked
            lines.append(f"Simulerte spill: {self.bets}, yield {roi:+.1%}. Med under ~1000 spill er usikkerheten "
                         "i yield typisk større enn ±5 prosentpoeng.")
            if self.clv:
                lines.append(f"Snitt CLV mot sluttodds: {sum(self.clv) / len(self.clv):+.2%} (n={len(self.clv)})")
        else:
            lines.append("Ingen spill passerte terskelen.")
        lines += ["", "Forbehold: én liga/sesong er et lite utvalg. Markedet er vanskelig å slå; en modell som ikke",
                  "slår markedsreferansen på log loss skal ikke brukes med høy vekt. Positiv yield i et lite utvalg",
                  "er ikke bevis på lønnsomhet."]
        return "\n".join(lines)


def run(rows: list[Row], weight: float = 0.25, min_edge: float = 0.03, warmup_days: int = 120,
        refit_days: int = 7) -> Report:
    rep = Report()
    if not rows:
        return rep
    hist = [HistMatch(r.d, 0, r.home, r.away, r.hg, r.ag) for r in rows]
    start = rows[0].d + timedelta(days=warmup_days)
    ratings, fit_date = None, None
    for r in rows:
        if r.d < start or not r.open_odds:
            continue
        if ratings is None or (r.d - fit_date).days >= refit_days:
            ratings, fit_date = fit(hist, r.d), r.d   # fit() bruker kun kamper før r.d
        eg = ratings.expected_goals(r.home, r.away)
        if not eg:
            continue
        market = devig_power(list(r.open_odds))
        model = []
        for o in "HDA":
            dist = result_distribution(Selection("1X2", o), *eg, ratings.rho)
            model.append(dist.get(Result.WON, 0.0))
        s = sum(model)
        model = [x / s for x in model]
        blend = [m + weight * (x - m) for m, x in zip(market, model)]
        actual = 0 if r.hg > r.ag else 1 if r.hg == r.ag else 2
        for name, p in (("marked", market), ("modell", model), ("blanding", blend)):
            rep.ll[name] += -math.log(max(p[actual], 1e-9))
            rep.brier[name] += sum((p[i] - (1 if i == actual else 0)) ** 2 for i in range(3))
        for i in range(3):
            b = min(9, int(blend[i] * 10))
            rep.calib[b][0] += 1
            rep.calib[b][1] += blend[i]
            rep.calib[b][2] += 1 if i == actual else 0
        rep.n += 1
        rep.first = rep.first or r.d
        rep.last = r.d
        if r.bet_odds:
            n_eff = min(ratings.n_eff.get(r.home, 0), ratings.n_eff.get(r.away, 0))
            unc = 0.015 + min(0.06, 0.15 / math.sqrt(max(n_eff, 1)))
            for i in range(3):
                o = r.bet_odds[i]
                if (blend[i] - unc) * o - 1 >= min_edge:
                    rep.bets += 1
                    rep.staked += 1
                    rep.returned += o if i == actual else 0
                    if r.close_odds:
                        rep.clv.append(o / r.close_odds[i] - 1)
    return rep


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Tidsbasert backtest av modellen mot markedet")
    ap.add_argument("csv", nargs="+", help="CSV-filer i football-data.co.uk-format")
    ap.add_argument("--weight", type=float, default=0.25)
    ap.add_argument("--min-edge", type=float, default=0.03)
    a = ap.parse_args(argv)
    rows = []
    for p in a.csv:
        rows += load_csv(p)
    rows.sort(key=lambda r: r.d)
    print(run(rows, a.weight, a.min_edge).text())
