"""Analyse: fra dagens kamper til rangerte, begrunnede enkeltspill.

Sannsynligheter:
  q_marked  = median av marginfrie (power-metoden) sannsynligheter fra referansebookmakere
  q_modell  = tidsvektet Poisson/Dixon-Coles (uvalidert)
  q         = q_marked + w·(q_modell − q_marked)   (krymping; w = config.model_weight)
  q_kons    = q − usikkerhet  (usikkerhet øker ved lite datagrunnlag)
  EV        = (1 − push)·(q·odds − 1)   der push er andelen tilbakebetaling (DNB/hele linjer)

Ingen subjektiv score brukes som sannsynlighet.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import median

from .config import Config
from .markets import MARKET_GROUP, Selection, selection_label
from .model import Ratings, fit, price_equivalent, result_distribution
from .probability import consensus, devig_power, implied
from .providers.base import Absence, Fixture, HistMatch, OddsQuote, ProviderError

log = logging.getLogger(__name__)

LEG_MIN_EV = -0.045  # Laveste punkt-EV for at et spill kan brukes som ledd

TRIPLES = {"1X2": ["H", "D", "A"], "1H_1X2": ["H", "D", "A"]}


def group_key(sel: Selection) -> tuple:
    m = sel.market
    if m in TRIPLES:
        return (m,)
    if m == "AH":
        return ("AH", sel.line if sel.outcome == "H" else -sel.line)
    if m in ("OU", "TT_H", "TT_A", "1H_OU", "CARDS_OU", "CORNERS_OU"):
        return (m, sel.line)
    if m in ("BTTS", "DNB"):
        return (m,)
    return (m, sel.outcome)  # DC håndteres separat


def group_members(gk: tuple) -> list[Selection]:
    m = gk[0]
    if m in TRIPLES:
        return [Selection(m, o) for o in TRIPLES[m]]
    if m == "AH":
        return [Selection("AH", "H", gk[1]), Selection("AH", "A", -gk[1])]
    if m in ("OU", "TT_H", "TT_A", "1H_OU", "CARDS_OU", "CORNERS_OU"):
        return [Selection(m, "O", gk[1]), Selection(m, "U", gk[1])]
    if m == "BTTS":
        return [Selection("BTTS", "Y"), Selection("BTTS", "N")]
    if m == "DNB":
        return [Selection("DNB", "H"), Selection("DNB", "A")]
    return []


def market_probabilities(quotes: list[OddsQuote]) -> dict[Selection, tuple[float, int]]:
    """Marginfri konsensus per valg -> (q, antall bookmakere)."""
    by_book: dict[str, dict[Selection, float]] = defaultdict(dict)
    for q in quotes:
        if not q.is_nt:
            by_book[q.bookmaker][q.selection] = q.odds
    groups: dict[tuple, list[list[float]]] = defaultdict(list)
    for book, sels in by_book.items():
        seen = set()
        for s in sels:
            if s.market == "DC":
                continue
            gk = group_key(s)
            if gk in seen:
                continue
            seen.add(gk)
            mem = group_members(gk)
            if mem and all(m in sels for m in mem):
                groups[gk].append(devig_power([sels[m] for m in mem]))
    out: dict[Selection, tuple[float, int]] = {}
    for gk, plist in groups.items():
        cons = consensus(plist)
        if cons:
            for s, p in zip(group_members(gk), cons):
                out[s] = (p, len(plist))
    if ("1X2",) in groups:
        ph, pd, pa = (out[Selection("1X2", o)][0] for o in "HDA")
        n = out[Selection("1X2", "H")][1]
        out[Selection("DC", "1X")] = (ph + pd, n)
        out[Selection("DC", "X2")] = (pa + pd, n)
        out[Selection("DC", "12")] = (ph + pa, n)
    return out


@dataclass
class Candidate:
    fixture: Fixture
    selection: Selection
    label: str
    odds: float
    odds_source: str           # f.eks. "Norsk Tipping (manuelt kontrollert)" / "Referanse: Pinnacle"
    odds_kind: str             # NT_KONTROLLERT / NT_TREDJEPART / NT_DEMO / REFERANSE
    odds_checked_at: datetime
    ref_odds: float | None
    market_q: float | None
    model_q: float | None
    final_q: float
    push: float
    unc: float
    ev_point: float
    ev_cons: float
    min_odds: float
    quality: float
    tags: list[str]
    analysis: dict = field(default_factory=dict)

    @property
    def hit(self) -> float:
        """Grovt anslag for at leddet ikke taper (vunnet eller tilbakebetalt)."""
        return min(0.99, self.final_q * (1 - self.push) + self.push)

    @property
    def score(self) -> float:
        return self.ev_cons + 0.02 * self.quality


@dataclass
class FixtureContext:
    fixture: Fixture
    ratings: Ratings | None
    quotes: list[OddsQuote]
    nt_quotes: list[OddsQuote]
    absences: list[Absence] | None
    history: list[HistMatch]
    quality: float = 0.0
    quality_notes: list[str] = field(default_factory=list)
    exp_goals: tuple[float, float] | None = None
    facts: dict = field(default_factory=dict)


def data_quality(ctx: FixtureContext) -> tuple[float, list[str]]:
    notes: list[str] = []
    q = 0.0
    r = ctx.ratings
    n = min(r.n_eff.get(ctx.fixture.home, 0), r.n_eff.get(ctx.fixture.away, 0)) if r else 0
    q += 0.35 * min(1.0, n / 20)
    if n < 10:
        notes.append(f"Lite historikk (effektivt {n:.0f} kamper for laget med minst data)")
    books = len({x.bookmaker for x in ctx.quotes if not x.is_nt})
    q += 0.25 * min(1.0, books / 3)
    if books < 2:
        notes.append("Færre enn to referansebookmakere – markedskonsensus svak")
    if ctx.nt_quotes:
        q += 0.15
    else:
        notes.append("Ingen Norsk Tipping-pris tilgjengelig")
    if ctx.absences is not None:
        q += 0.15
    else:
        notes.append("Fraværsliste mangler")
    if r and r.xg_share > 0.5:
        q += 0.10
    else:
        notes.append("xG mangler i historikken – modellen bygger på mål")
        q += 0.03
    return round(q, 3), notes


def _form(team: str, matches: list[HistMatch], r: Ratings) -> dict:
    res, pts, gd, exp_gd, xg_for, xg_ag, home_g, away_g = [], 0, 0, 0.0, [], [], [], []
    for m in matches[:5]:
        is_home = m.home == team
        gf, ga = (m.hg, m.ag) if is_home else (m.ag, m.hg)
        res.append("V" if gf > ga else "U" if gf == ga else "T")
        pts += 3 if gf > ga else 1 if gf == ga else 0
        gd += gf - ga
        eg = r.expected_goals(m.home, m.away)
        if eg:
            exp_gd += (eg[0] - eg[1]) if is_home else (eg[1] - eg[0])
    for m in matches[:10]:
        is_home = m.home == team
        if m.hxg is not None:
            xg_for.append(m.hxg if is_home else m.axg)
            xg_ag.append(m.axg if is_home else m.hxg)
        (home_g if is_home else away_g).append(m.hg if is_home else m.ag)
    return {
        "siste5": "".join(res), "poeng5": pts, "mf5": gd, "forventet_mf5": round(exp_gd, 2),
        "over_forventning": round(gd - exp_gd, 2),
        "xg_for": round(sum(xg_for) / len(xg_for), 2) if xg_for else None,
        "xg_mot": round(sum(xg_ag) / len(xg_ag), 2) if xg_ag else None,
        "mål_hjemme_snitt": round(sum(home_g) / len(home_g), 2) if home_g else None,
        "mål_borte_snitt": round(sum(away_g) / len(away_g), 2) if away_g else None,
        "siste_kamp": matches[0].date.isoformat() if matches else None,
    }


def _table(history: list[HistMatch], season_start: date | None) -> dict[str, int]:
    pts: dict[str, int] = defaultdict(int)
    gd: dict[str, int] = defaultdict(int)
    for m in history:
        if season_start and m.date < season_start:
            continue
        pts[m.home] += 3 if m.hg > m.ag else 1 if m.hg == m.ag else 0
        pts[m.away] += 3 if m.ag > m.hg else 1 if m.hg == m.ag else 0
        gd[m.home] += m.hg - m.ag
        gd[m.away] += m.ag - m.hg
    order = sorted(pts, key=lambda t: (pts[t], gd[t]), reverse=True)
    return {t: i + 1 for i, t in enumerate(order)}


def build_facts(ctx: FixtureContext, analysis_day: date) -> dict:
    fx, r = ctx.fixture, ctx.ratings
    facts: dict = {"kamp": f"{fx.home} – {fx.away}", "liga": fx.league_name, "dommer": fx.referee}
    if not r or not r.attack:
        return facts
    for side, team in (("hjemme", fx.home), ("borte", fx.away)):
        recent = r.recent.get(team, [])
        f = _form(team, recent, r)
        f["angrep_indeks"] = round(r.attack.get(team, r.league_avg) / r.league_avg, 2)
        f["forsvar_indeks"] = round(r.defence.get(team, 1.0), 2)  # >1 = svakere enn snittet
        f["effektive_kamper"] = round(r.n_eff.get(team, 0), 1)
        if recent:
            f["hviledager"] = (analysis_day - recent[0].date).days
        facts[side] = f
    h2h = [m for m in sorted(ctx.history, key=lambda m: m.date, reverse=True)
           if {m.home, m.away} == {fx.home, fx.away} and m.date < analysis_day][:3]
    facts["innbyrdes"] = [f"{m.date.isoformat()}: {m.home} {m.hg}–{m.ag} {m.away}" for m in h2h]
    season_matches = [m for m in ctx.history if m.date < analysis_day]
    if season_matches:
        latest = max(m.date for m in season_matches)
        table = _table(season_matches, latest - timedelta(days=300))
        facts["tabell"] = {fx.home: table.get(fx.home), fx.away: table.get(fx.away), "lag_totalt": len(table)}
    if ctx.exp_goals:
        facts["forventede_mål"] = {"hjemme": round(ctx.exp_goals[0], 2), "borte": round(ctx.exp_goals[1], 2),
                                   "ligasnitt_per_lag": round(r.league_avg, 2)}
    if ctx.absences is not None:
        facts["fravær"] = [{"lag": a.team, "spiller": a.player, "status": a.kind, "årsak": a.reason}
                           for a in ctx.absences]
    return facts


def reasons(c: Candidate, ctx: FixtureContext) -> tuple[list[str], list[str], list[str]]:
    """Argumenter for, mot og trekk-vilkår – bygget kun fra faktiske data."""
    fx, sel = ctx.fixture, c.selection
    pro: list[str] = []
    con: list[str] = []
    f = ctx.facts
    h, a = f.get("hjemme"), f.get("borte")
    eg = ctx.exp_goals
    group = MARKET_GROUP.get(sel.market, "")

    if c.market_q is not None:
        fair = 1 / c.market_q
        if c.odds > fair * 1.02:
            pro.append(f"Tilbudt odds {c.odds:.2f} er tydelig høyere enn markedets marginfrie pris {fair:.2f}.")
        elif c.odds < fair * 0.98:
            con.append(f"Tilbudt odds {c.odds:.2f} er lavere enn markedets marginfrie pris {fair:.2f} – "
                       "prisen inneholder margin.")
    if c.hit >= 0.62:
        pro.append(f"Anslått treffmulighet ca. {c.hit:.0%} (høy treffmulighet er ikke det samme som god pris).")
    if c.model_q is not None and c.market_q is not None:
        d = c.model_q - c.market_q
        if d > 0.02:
            pro.append(f"Modellen anslår {c.model_q:.0%} mot markedets {c.market_q:.0%} (uvalidert modell).")
        elif d < -0.02:
            con.append(f"Modellen er mer negativ ({c.model_q:.0%}) enn markedet ({c.market_q:.0%}).")

    if eg and group in ("Mål", "Begge lag scorer", "1. omgang"):
        tot = eg[0] + eg[1]
        lavg = f.get("forventede_mål", {}).get("ligasnitt_per_lag", 1.35) * 2
        txt = f"Forventede mål {eg[0]:.2f}–{eg[1]:.2f} (sum {tot:.2f}, ligasnitt {lavg:.2f})."
        wants_goals = sel.outcome in ("O", "Y")
        (pro if (tot > lavg) == wants_goals else con).append(txt)
        if h and a and h.get("xg_for") is not None:
            pro_or_con = pro if ((h["xg_for"] + a["xg_for"]) / 2 > lavg / 2) == wants_goals else con
            pro_or_con.append(f"xG for siste 10: {fx.home} {h['xg_for']}, {fx.away} {a['xg_for']}.")
    if eg and group in ("Kampvinner", "Handikap"):
        picked_home = sel.outcome in ("H", "1X")
        picked_away = sel.outcome in ("A", "X2")
        diff = eg[0] - eg[1]
        if picked_home or picked_away:
            fav_team = fx.home if diff > 0 else fx.away
            if abs(diff) < 0.15:
                con.append(f"Jevn kamp ifølge modellen (forventet målforskjell {abs(diff):.2f}).")
            else:
                fav = (diff > 0) == picked_home
                (pro if fav else con).append(f"Modellen venter {abs(diff):.2f} mål i favør av {fav_team}.")
        if h and a:
            team, tf = (fx.home, h) if picked_home else (fx.away, a) if picked_away else (None, None)
            if tf:
                if tf.get("over_forventning", 0) > 2:
                    con.append(f"{team} har {tf['over_forventning']:+.1f} i målforskjell over forventning siste 5 – "
                               "resultatene kan være preget av flaks.")
                elif tf.get("over_forventning", 0) < -2:
                    pro.append(f"{team} har prestert under forventning siste 5 ({tf['over_forventning']:+.1f}); "
                               "underliggende nivå kan være bedre enn resultatene.")
    for side, team in (("hjemme", fx.home), ("borte", fx.away)):
        t = f.get(side) or {}
        if t.get("hviledager") is not None and t["hviledager"] <= 3:
            con.append(f"{team} har bare {t['hviledager']} hviledager.")
        if t.get("effektive_kamper", 99) < 10:
            con.append(f"Lite datagrunnlag for {team}.")
    out_players = [x for x in f.get("fravær", []) if x["status"] == "Ute"]
    if out_players:
        by_team: dict[str, list[str]] = defaultdict(list)
        for x in out_players:
            by_team[x["lag"]].append(x["spiller"])
        con.append("Kjente fravær: " + "; ".join(f"{t}: {', '.join(p)}" for t, p in by_team.items())
                   + ". Betydningen av hver spiller er ikke tallfestet i modellen.")
    elif ctx.absences is None:
        con.append("Fraværsliste mangler – lagnyheter er ikke kontrollert.")
    if sel.market in ("AH", "OU", "TT_H", "TT_A") and sel.line is not None and abs(sel.line) % 0.5 == 0.25:
        con.append("Kvartlinje: mulig halv gevinst/halvt tap.")
    if not con:
        con.append("Uvalidert modell og vanlig kampvarians; ingen konkrete motargumenter i dataene.")

    withdraw = [f"Odds faller under {c.min_odds:.2f}.",
                "Bekreftet startoppstilling viser vesentlige fravær som ikke er kjent nå (keeper, midtstopper, toppscorer).",
                "Kampen flyttes, eller markedet endrer navn/regler hos Norsk Tipping."]
    return pro, con, withdraw


class Analyzer:
    def __init__(self, cfg: Config, provider, nt_sources: list):
        self.cfg = cfg
        self.provider = provider
        self.nt_sources = nt_sources

    async def load_contexts(self, fixtures: list[Fixture], analysis_day: date) -> tuple[list[FixtureContext], list[str]]:
        problems: list[str] = []
        by_league: dict[tuple[int, int], list[Fixture]] = defaultdict(list)
        for f in fixtures:
            by_league[(f.league_id, f.season)].append(f)
        ctxs: list[FixtureContext] = []
        for (lid, season), fxs in by_league.items():
            try:
                hist = await self.provider.history(lid, season)
            except ProviderError as e:
                problems.append(f"Historikk mangler for {fxs[0].league_name}: {e}")
                hist = []
            ratings = fit(hist, analysis_day) if hist else None
            for fx in fxs:
                try:
                    quotes = await self.provider.odds(fx)
                except ProviderError as e:
                    problems.append(f"Odds mangler for {fx.home}–{fx.away}: {e}")
                    quotes = []
                nt: list[OddsQuote] = []
                for src in self.nt_sources:
                    try:
                        nt += await src.nt_odds(fx)
                    except Exception as e:  # noqa: BLE001 – én kilde skal ikke stoppe analysen
                        problems.append(f"NT-kilde {getattr(src, 'name', src)} feilet: {e}")
                try:
                    absn = await self.provider.absences(fx)
                except ProviderError:
                    absn = None
                ctx = FixtureContext(fx, ratings, quotes, nt, absn, hist)
                ctx.exp_goals = ratings.expected_goals(fx.home, fx.away) if ratings else None
                ctx.quality, ctx.quality_notes = data_quality(ctx)
                ctx.facts = build_facts(ctx, analysis_day)
                ctxs.append(ctx)
        return ctxs, problems

    def _best_nt(self, nt: list[OddsQuote], sel: Selection, now: datetime) -> OddsQuote | None:
        max_age = timedelta(minutes=self.cfg.max_odds_age_minutes)
        cands = [q for q in nt if q.selection == sel and now - q.checked_at <= max_age]
        if not cands:
            return None
        # Manuelt kontrollert pris har forrang; ellers nyeste.
        cands.sort(key=lambda q: (q.nt_verified, q.checked_at), reverse=True)
        return cands[0]

    def evaluate(self, ctx: FixtureContext, now: datetime) -> list[Candidate]:
        cfg = self.cfg
        mk = market_probabilities(ctx.quotes)
        sels = set(mk) | {q.selection for q in ctx.nt_quotes}
        out: list[Candidate] = []
        r = ctx.ratings
        n_min = min(r.n_eff.get(ctx.fixture.home, 0), r.n_eff.get(ctx.fixture.away, 0)) if r else 0
        for sel in sels:
            if sel.market == "CARDS_OU" and not cfg.enable_cards:
                continue
            if sel.market == "CORNERS_OU" and not cfg.enable_corners:
                continue
            market = mk.get(sel)
            if market is None:
                continue  # Uten markedskonsensus anbefaler vi ikke
            q_market, nbooks = market
            dist = result_distribution(sel, *ctx.exp_goals, r.rho) if (ctx.exp_goals and r) else None
            q_model, push = price_equivalent(dist) if dist else (None, 0.0)
            if dist is None:
                push = 0.0
            q = q_market + cfg.model_weight * (q_model - q_market) if q_model is not None else q_market
            unc = 0.015 + min(0.06, 0.15 / math.sqrt(max(n_min, 1))) + (0.01 if nbooks < 3 else 0)
            if q_model is None:
                unc += 0.01
            nt = self._best_nt(ctx.nt_quotes, sel, now)
            refs = [x.odds for x in ctx.quotes if x.selection == sel and not x.is_nt]
            ref_med = round(median(refs), 2) if refs else None
            if nt:
                odds = nt.odds
                if nt.nt_verified:
                    kind, src = "NT_KONTROLLERT", "Norsk Tipping (manuelt kontrollert)"
                elif nt.source == "demo":
                    kind, src = "NT_DEMO", "DEMO-pris (fiktiv)"
                else:
                    kind, src = "NT_TREDJEPART", f"Norsk Tipping via {nt.source} – kontroller i Oddsen"
                checked = nt.checked_at
            elif ref_med:
                odds = ref_med
                kind, src = "REFERANSE", f"Median av {len(refs)} referansebookmakere – ikke verifisert hos Norsk Tipping"
                checked = max(x.checked_at for x in ctx.quotes if x.selection == sel)
            else:
                continue
            ev_point = (1 - push) * (q * odds - 1)
            q_cons = max(0.001, q - unc)
            ev_cons = (1 - push) * (q_cons * odds - 1)
            tags = []
            if ev_cons >= cfg.min_edge:
                tags.append("verdi")
            hit = q * (1 - push) + push
            if hit >= 0.62 and ev_point >= -0.04:
                tags.append("høy_treff")
            if odds >= 3.0 and ev_point >= -0.04:
                tags.append("høy_odds")
            if q_model is not None and q_model < q_market - 0.03:
                tags.append("modell_uenig")
            # Minste akseptable odds: verdispill -> der konservativ EV faller under min_edge;
            # øvrige -> der punkt-EV faller under kvalifiseringsgrensen (LEG_MIN_EV).
            if "verdi" in tags:
                min_odds = (1 + cfg.min_edge / max(1 - push, 0.01)) / q_cons
            else:
                min_odds = (1 + LEG_MIN_EV / max(1 - push, 0.01)) / q
            cand = Candidate(ctx.fixture, sel, selection_label(sel, ctx.fixture.home, ctx.fixture.away), odds, src,
                             kind, checked, ref_med, q_market, q_model, q, push, unc, ev_point, ev_cons, min_odds,
                             ctx.quality, tags)
            pro, con, withdraw = reasons(cand, ctx)
            cand.analysis = {
                "for": pro, "mot": con, "trekk_hvis": withdraw, "fakta": ctx.facts,
                "datakvalitet": ctx.quality, "datamangler": ctx.quality_notes,
                "bookmakere": nbooks, "rå_implisitt": round(implied(odds), 4),
                "taktikk": "Taktisk analyse (formasjon, press, omstillinger) er ikke tilgjengelig i datagrunnlaget "
                           "og inngår ikke i estimatet.",
            }
            out.append(cand)
        return out

    def eligible_leg(self, c: Candidate) -> bool:
        cfg = self.cfg
        return (c.quality >= cfg.min_quality and cfg.min_leg_odds <= c.odds <= cfg.max_single_odds
                and c.ev_point >= LEG_MIN_EV and "modell_uenig" not in c.tags)

    def shortlist(self, cands: list[Candidate], max_per_fixture: int = 3) -> list[Candidate]:
        """Rangert liste: verdi først, deretter høy treffmulighet. Maks n per kamp."""
        per_fx: dict[str, int] = defaultdict(int)
        out = []
        for c in sorted(cands, key=lambda c: c.score, reverse=True):
            if not self.eligible_leg(c):
                continue
            if per_fx[c.fixture.id] >= max_per_fixture:
                continue
            per_fx[c.fixture.id] += 1
            out.append(c)
        return out
