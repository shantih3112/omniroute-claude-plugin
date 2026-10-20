"""Markedsdefinisjoner, norske navn, oppgjørsregler og oppgjør.

Oppgjørsreglene her er vanlige bransjeregler. Norsk Tippings egne spilleregler er
gjeldende ved innlevering og kan avvike (f.eks. ved kort, utsatte kamper eller
asiatiske linjer). Boten skriver derfor alltid at NTs oppgjør er det som gjelder.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Result(str, Enum):
    WON = "WON"
    LOST = "LOST"
    VOID = "VOID"
    HALF_WON = "HALF_WON"
    HALF_LOST = "HALF_LOST"


RESULT_NO = {
    Result.WON: "Vunnet",
    Result.LOST: "Tapt",
    Result.VOID: "Annullert (tilbakebetaling)",
    Result.HALF_WON: "Halvt vunnet",
    Result.HALF_LOST: "Halvt tapt",
}


def payout_factor(result: Result, odds: float) -> float:
    """Returnert beløp per innsatsenhet for ett ledd (brukes også i kombinasjoner)."""
    return {
        Result.WON: odds,
        Result.LOST: 0.0,
        Result.VOID: 1.0,
        Result.HALF_WON: (odds + 1.0) / 2.0,
        Result.HALF_LOST: 0.5,
    }[result]


class LiveState(str, Enum):
    LIVE = "LEVER"
    LIKELY_WON = "VIRKER_VUNNET"
    LIKELY_LOST = "VIRKER_TAPT"


@dataclass(frozen=True)
class Selection:
    market: str          # 1X2, DC, DNB, AH, OU, BTTS, TT_H, TT_A, 1H_1X2, 1H_OU, CARDS_OU, CORNERS_OU
    outcome: str         # H/D/A, 1X/12/X2, O/U, Y/N
    line: float | None = None  # For AH: linjen sett fra valgt lag. For totaler: grensen.

    def key(self) -> str:
        return f"{self.market}:{self.outcome}:{'' if self.line is None else f'{self.line:+g}' if self.market == 'AH' else f'{self.line:g}'}"

    @classmethod
    def from_key(cls, key: str) -> "Selection":
        m, o, l = key.split(":")
        return cls(m, o, float(l) if l else None)


@dataclass
class MatchStats:
    """Tall for oppgjør. Ordinær tid (90 min + tillegg) med mindre annet er oppgitt."""
    home_goals: int
    away_goals: int
    ht_home: int | None = None
    ht_away: int | None = None
    cards: int | None = None      # Gule + røde, hvert kort teller 1
    corners: int | None = None


MARKET_NAMES = {
    "1X2": "Fulltid H-U-B",
    "DC": "Dobbeltsjanse",
    "DNB": "Draw no bet (uavgjort gir tilbakebetaling)",
    "AH": "Asiatisk handikap",
    "OU": "Totalt antall mål",
    "BTTS": "Begge lag scorer",
    "TT_H": "Hjemmelagets antall mål",
    "TT_A": "Bortelagets antall mål",
    "1H_1X2": "1. omgang H-U-B",
    "1H_OU": "Mål i 1. omgang",
    "CARDS_OU": "Totalt antall kort",
    "CORNERS_OU": "Totalt antall hjørnespark",
}

MARKET_GROUP = {
    "1X2": "Kampvinner", "DC": "Kampvinner", "DNB": "Kampvinner", "AH": "Handikap",
    "OU": "Mål", "TT_H": "Mål", "TT_A": "Mål", "1H_OU": "Mål", "1H_1X2": "1. omgang",
    "BTTS": "Begge lag scorer", "CARDS_OU": "Kort", "CORNERS_OU": "Hjørnespark",
}


def selection_label(sel: Selection, home: str, away: str) -> str:
    m, o, l = sel.market, sel.outcome, sel.line
    team = {"H": home, "A": away}
    if m in ("1X2", "1H_1X2"):
        txt = {"H": f"{home} vinner", "D": "Uavgjort", "A": f"{away} vinner"}[o]
        return txt + (" (1. omgang)" if m == "1H_1X2" else "")
    if m == "DC":
        return {"1X": f"{home} eller uavgjort", "X2": f"{away} eller uavgjort", "12": f"{home} eller {away}"}[o]
    if m == "DNB":
        return f"{team[o]} (draw no bet)"
    if m == "AH":
        return f"{team[o]} {l:+g} (asiatisk)"
    ou = {"O": "Over", "U": "Under"}
    if m == "OU":
        return f"{ou[o]} {l:g} mål"
    if m == "1H_OU":
        return f"{ou[o]} {l:g} mål i 1. omgang"
    if m == "TT_H":
        return f"{home} {ou[o].lower()} {l:g} mål"
    if m == "TT_A":
        return f"{away} {ou[o].lower()} {l:g} mål"
    if m == "BTTS":
        return "Begge lag scorer: Ja" if o == "Y" else "Begge lag scorer: Nei"
    if m == "CARDS_OU":
        return f"{ou[o]} {l:g} kort"
    if m == "CORNERS_OU":
        return f"{ou[o]} {l:g} hjørnespark"
    return sel.key()


def settlement_rule(sel: Selection) -> str:
    """Kort norsk forklaring av oppgjør, med særregler."""
    m, l = sel.market, sel.line
    base = "Gjelder ordinær tid (90 min + tilleggstid), ikke ekstraomganger eller straffer."
    if m == "DNB":
        return base + " Uavgjort gir full tilbakebetaling (ledd teller 1,00 i kombinasjon)."
    if m in ("AH", "OU", "TT_H", "TT_A", "1H_OU", "CARDS_OU", "CORNERS_OU") and l is not None:
        frac = abs(l) % 1
        if abs(frac - 0.25) < 1e-9 or abs(frac - 0.75) < 1e-9:
            return base + (f" Kvartlinje: innsatsen deles på {_split(l)[0]:g} og {_split(l)[1]:g}."
                           " Mulig halv gevinst eller halvt tap.")
        if abs(frac) < 1e-9:
            return base + " Helt tall: treffer resultatet linjen nøyaktig, tilbakebetales innsatsen."
    if m == "CARDS_OU":
        return base + (" Boten teller hvert gult og rødt kort som 1. Telleregel (f.eks. andre gule)"
                       " varierer mellom spillselskap – kontroller NTs regel.")
    if m in ("1H_1X2", "1H_OU"):
        return "Gjelder kun 1. omgang inkl. tilleggstid."
    return base


def _split(line: float) -> tuple[float, float]:
    return (line - 0.25, line + 0.25)


def _settle_line(diff: float) -> Result:
    if diff > 0:
        return Result.WON
    if diff < 0:
        return Result.LOST
    return Result.VOID


def _combine(a: Result, b: Result) -> Result:
    pair = {a, b}
    if pair == {Result.WON}:
        return Result.WON
    if pair == {Result.LOST}:
        return Result.LOST
    if pair == {Result.VOID}:
        return Result.VOID
    if pair == {Result.WON, Result.VOID}:
        return Result.HALF_WON
    if pair == {Result.LOST, Result.VOID}:
        return Result.HALF_LOST
    raise ValueError(f"umulig kvartlinje-kombinasjon {a} {b}")


def _is_quarter(line: float) -> bool:
    frac = abs(line) % 1
    return abs(frac - 0.25) < 1e-9 or abs(frac - 0.75) < 1e-9


def _over_under(total: float, line: float, outcome: str) -> Result:
    sign = 1 if outcome == "O" else -1
    if _is_quarter(line):
        a, b = _split(line)
        return _combine(_settle_line(sign * (total - a)), _settle_line(sign * (total - b)))
    return _settle_line(sign * (total - line))


def settle(sel: Selection, s: MatchStats) -> Result | None:
    """Gjør opp et valg. Returnerer None hvis nødvendige data mangler."""
    h, a = s.home_goals, s.away_goals
    m, o, l = sel.market, sel.outcome, sel.line
    if m == "1X2":
        res = "H" if h > a else "A" if a > h else "D"
        return Result.WON if res == o else Result.LOST
    if m == "1H_1X2":
        if s.ht_home is None or s.ht_away is None:
            return None
        res = "H" if s.ht_home > s.ht_away else "A" if s.ht_away > s.ht_home else "D"
        return Result.WON if res == o else Result.LOST
    if m == "DC":
        res = "H" if h > a else "A" if a > h else "D"
        ok = {"1X": ("H", "D"), "X2": ("A", "D"), "12": ("H", "A")}[o]
        return Result.WON if res in ok else Result.LOST
    if m == "DNB":
        if h == a:
            return Result.VOID
        return Result.WON if (h > a) == (o == "H") else Result.LOST
    if m == "AH":
        assert l is not None
        margin = (h - a) if o == "H" else (a - h)
        if _is_quarter(l):
            x, y = _split(l)
            return _combine(_settle_line(margin + x), _settle_line(margin + y))
        return _settle_line(margin + l)
    if m == "OU":
        return _over_under(h + a, l, o)
    if m == "TT_H":
        return _over_under(h, l, o)
    if m == "TT_A":
        return _over_under(a, l, o)
    if m == "1H_OU":
        if s.ht_home is None or s.ht_away is None:
            return None
        return _over_under(s.ht_home + s.ht_away, l, o)
    if m == "BTTS":
        both = h > 0 and a > 0
        return Result.WON if both == (o == "Y") else Result.LOST
    if m == "CARDS_OU":
        return None if s.cards is None else _over_under(s.cards, l, o)
    if m == "CORNERS_OU":
        return None if s.corners is None else _over_under(s.corners, l, o)
    raise ValueError(f"ukjent marked {m}")


def live_state(sel: Selection, s: MatchStats, first_half_over: bool = False) -> LiveState:
    """Tilstand under kamp. Bare monotone markeder kan 'virke avgjort' før slutt.

    Kampvinner/handikap merkes ALDRI tapt underveis – laget kan snu kampen.
    "Virker avgjort" er ikke bekreftet: mål kan annulleres (VAR) og data korrigeres.
    """
    h, a = s.home_goals, s.away_goals
    m, o, l = sel.market, sel.outcome, sel.line

    def mono(total: float) -> LiveState:
        assert l is not None
        top = l + 0.25 if _is_quarter(l) else l
        if total > top:
            return LiveState.LIKELY_WON if o == "O" else LiveState.LIKELY_LOST
        return LiveState.LIVE

    if m == "OU":
        return mono(h + a)
    if m == "TT_H":
        return mono(h)
    if m == "TT_A":
        return mono(a)
    if m == "BTTS" and h > 0 and a > 0:
        return LiveState.LIKELY_WON if o == "Y" else LiveState.LIKELY_LOST
    if m == "CARDS_OU" and s.cards is not None:
        return mono(s.cards)
    if m == "CORNERS_OU" and s.corners is not None:
        return mono(s.corners)
    if m == "1H_OU" and s.ht_home is not None and s.ht_away is not None:
        st = mono(s.ht_home + s.ht_away)
        if st == LiveState.LIVE and first_half_over:
            r = settle(sel, s)
            return LiveState.LIKELY_WON if r in (Result.WON, Result.HALF_WON) else LiveState.LIKELY_LOST
        return st
    return LiveState.LIVE
