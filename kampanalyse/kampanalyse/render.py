"""Alle Telegram-tekster. HTML-format, korte avsnitt, få emojier, ingen brede tabeller.

Ordbruk: aldri «banker», «gratis penger», «sikker gevinst» eller «garantert».
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime

from .coupons import BAND_BY_CODE
from .db import DB
from .markets import RESULT_NO, MARKET_NAMES, Result, Selection, settlement_rule
from .repo import PickView, coupon_latest, coupon_legs
from .timeutil import from_iso, hm, nice_date, stamp

BOT_NAME = "Kampanalysen"
BOT_SHORT = "Nøktern fotballanalyse og spillforslag tilpasset Norsk Tipping. Ingen garantier."
BOT_DESCRIPTION = (
    "Kampanalysen gir daglig morgenbrief med analyserte enkeltspill og kombinasjoner, "
    "følger kampene automatisk og rapporterer resultater åpent. Forslagene er analyser, "
    "ikke garantier. Du leverer selv eventuelle spill hos Norsk Tipping. 18 år. "
    "Hjelpelinjen: 800 800 40."
)
RG_FOOTER = "<i>Spill ansvarlig. Ingen forslag er sikre. Hjelpelinjen: 800 800 40.</i>"
DEMO_BANNER = "🧪 <b>DEMO – EKSEMPELDATA.</b> Fiktive lag og odds, ikke dagens kamper.\n\n"

BANNED_WORDS = ["banker", "gratis penger", "sikker gevinst", "garantert"]

ODDS_KIND = {
    "NT_KONTROLLERT": "Norsk Tipping, kontrollert",
    "NT_TREDJEPART": "NT via tredjepart – kontroller i Oddsen",
    "NT_DEMO": "DEMO-pris (fiktiv)",
    "REFERANSE": "Ikke verifisert hos Norsk Tipping",
}
STATUS_NO = {"FORELØPIG": "foreløpig", "KONTROLLERT": "kontrollert", "STARTET": "startet", "AVGJORT": "avgjort"}
LIVE_NO = {None: "Ikke startet", "LEVER": "Lever", "VIRKER_VUNNET": "Virker vunnet (ikke bekreftet)",
           "VIRKER_TAPT": "Virker tapt (ikke bekreftet)", "AVSLUTTET": "Slutt – venter på bekreftelse",
           "UAVKLART": "Uavklart (utsatt/avbrutt) – følg NTs oppgjør"}


def e(s) -> str:
    return html.escape(str(s), quote=False)


def pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.0f} %"


def evp(x: float) -> str:
    return f"{x * 100:+.1f} %"


def _banner(demo: bool) -> str:
    return DEMO_BANNER if demo else ""


def leg_state(p: PickView) -> str:
    if p["result"]:
        return "✅ " + RESULT_NO[Result(p["result"])] if p["result"] in ("WON", "HALF_WON") else \
            ("➖ " if p["result"] == "VOID" else "❌ ") + RESULT_NO[Result(p["result"])]
    return LIVE_NO.get(p["live_state"], p["live_state"] or "Ikke startet")


def lineup_state(p: PickView) -> str:
    if p.fixture.get("lineups_at"):
        return "bekreftet"
    return "ikke publisert ennå"


def odds_line(p: PickView) -> str:
    kind = ODDS_KIND.get(p["odds_kind"], p["odds_kind"])
    return f"<b>{p['odds']:.2f}</b> · {e(kind)} · kontrollert {stamp(from_iso(p['odds_checked_at']))}"


def pick_block(p: PickView, n: int | None = None, compact: bool = False) -> str:
    f = p.fixture
    a = p.analysis
    head = f"{n}. " if n else ""
    lines = [f"{head}<b>{e(f['home'])} – {e(f['away'])}</b> · {hm(from_iso(f['kickoff']))}",
             f"{e(MARKET_NAMES.get(p['selection_key'].split(':')[0], ''))}: <b>{e(p['label'])}</b>",
             f"Odds: {odds_line(p)}"]
    if not compact:
        lines.append(f"Estimat: {pct(p['final_q'])} (konservativt {pct(max(0, p['final_q'] - p['unc']))}) · "
                     f"EV {evp(p['ev_point'])}")
        if a.get("for"):
            lines.append(f"For: {e(a['for'][0])}")
        if a.get("mot"):
            lines.append(f"Mot: {e(a['mot'][0])}")
        lines.append(f"Minste odds: {p['min_odds']:.2f} · Oppstilling: {lineup_state(p)}")
    return "\n".join(lines)


def tag_label(tags: list[str]) -> str:
    labels = []
    if "verdi" in tags:
        labels.append("God pris")
    if "høy_treff" in tags:
        labels.append("Høy treffmulighet")
    if "høy_odds" in tags:
        labels.append("Høy odds")
    return " · ".join(labels) or "Kvalifisert"


# ------------------------------------------------------------------ morgenbrief

def morning_brief(d: date, published: datetime, checked: datetime | None, picks: list[PickView],
                  coupons: list[dict], empty_bands: list[str], n_fixtures: int, n_screened: int,
                  problems: list[str], watch: list[str], next_update: str, demo: bool, db: DB) -> str:
    out = [_banner(demo) + f"🌅 <b>MORGENBRIEF | {e(nice_date(d)).upper()}</b>",
           f"Publisert: {hm(published)} · Data sist kontrollert: {hm(checked) if checked else 'ukjent'}", ""]
    out.append("<b>DAGENS OVERBLIKK</b>")
    out.append(f"{n_fixtures} kamper kartlagt, {n_screened} med godt nok datagrunnlag. "
               f"{len(picks)} enkeltspill kvalifisert, {len(coupons)} bonger.")
    if problems:
        out.append(f"⚠️ Datamangler: {e(problems[0])}" + (f" (+{len(problems) - 1} til)" if len(problems) > 1 else ""))
    out.append("")
    main = next((c for c in coupons if c["band"] == "B"), None)
    out.append("<b>HOVEDFORSLAG</b>")
    if main:
        legs = coupon_legs(db, main["id"], main["version"])
        weakest = min(legs, key=lambda p: p["final_q"])
        out.append(f"{e(main['id'])} · {len(legs)} ledd · totalodds <b>{main['total_odds']:.2f}</b>"
                   f"{'' if main['total_verified'] else ' (ikke verifisert hos NT)'}")
        out.append(f"Største usikkerhet: {e(weakest.fixture['home'])} – {e(weakest.fixture['away'])}, "
                   f"{e(weakest['label'])} ({pct(weakest['final_q'])}).")
    else:
        out.append("Ingen kvalifisert hovedbong i dag.")
    out.append("")
    out.append("<b>ØVRIGE BONGER</b>")
    for code in ["C", "D", "E", "F", "G"]:
        b = BAND_BY_CODE[code]
        c = next((c for c in coupons if c["band"] == code), None)
        if c:
            spec = " · spekulativ" if b.speculative else ""
            out.append(f"• {e(b.title)}: {e(c['id'])} · odds {c['total_odds']:.2f}{spec}")
        else:
            out.append(f"• {e(b.title)}: Ingen kvalifisert bong i denne kategorien")
    out.append("")
    out.append("<b>DAGENS ENKELTSPILL</b>")
    if picks:
        for i, p in enumerate(picks[:5], 1):
            out.append(f"{i}. {e(p.fixture['home'])} – {e(p.fixture['away'])} {hm(from_iso(p.fixture['kickoff']))}: "
                       f"{e(p['label'])} @ {p['odds']:.2f} · {e(tag_label(p.tags))}")
        if len(picks) > 5:
            out.append(f"…og {len(picks) - 5} til under /singles")
    else:
        out.append("Ingen enkeltspill oppfyller kravene i dag. Å stå over er et gyldig resultat.")
    out.append("")
    out.append("<b>DETTE FØLGER VI MED PÅ</b>")
    out += [f"• {e(w)}" for w in watch[:5]] or ["• Ingen spesielle forhold"]
    out.append("")
    out.append("<b>NESTE OPPDATERING</b>")
    out.append(e(next_update))
    out.append("")
    out.append(RG_FOOTER)
    return "\n".join(out)


def brief_markup(d: date) -> list:
    return [[["Enkeltspill", "m:singles"], ["Alle bonger", f"o:{d.isoformat()}"]],
            [["Kampstatus", "m:status"]]]


# ------------------------------------------------------------------ bong

def coupon_message(db: DB, cid: str, demo: bool) -> str:
    c = coupon_latest(db, cid)
    if not c:
        return "Fant ikke bongen."
    band = BAND_BY_CODE[c["band"]]
    legs = coupon_legs(db, cid, c["version"])
    status = STATUS_NO.get(c["status"], c["status"].lower())
    if c["outcome"]:
        status += f" – {RESULT_NO.get(Result(c['outcome']), c['outcome']) if c['outcome'] in Result.__members__ else c['outcome']}"
    out = [_banner(demo) + f"⚽ <b>{e(band.title.upper())}</b>" + (" · <i>spekulativ</i>" if band.speculative else ""),
           f"ID: <code>{e(cid)}</code> | Versjon: {c['version']}",
           f"Status: {e(status)}",
           f"Publisert: {stamp(from_iso(c['published_at'])) if c['published_at'] else 'ikke publisert'}",
           f"Odds kontrollert: {stamp(from_iso(c['odds_checked_at'])) if c['odds_checked_at'] else 'ukjent'}", ""]
    for i, p in enumerate(legs, 1):
        a = p.analysis
        out.append(f"<b>{i}. {e(p.fixture['home'])} – {e(p.fixture['away'])}</b> · {hm(from_iso(p.fixture['kickoff']))}")
        out.append(f"{e(MARKET_NAMES.get(p['selection_key'].split(':')[0], ''))}: <b>{e(p['label'])}</b>")
        out.append(f"Odds: {odds_line(p)}")
        if a.get("for"):
            out.append(f"Hvorfor: {e(a['for'][0])}")
        out.append(f"Usikkerhet: {e(a['mot'][0]) if a.get('mot') else 'Uvalidert modell'}")
        out.append(f"Oppstilling: {lineup_state(p)} · Status: {e(leg_state(p))}")
        out.append("")
    out.append("<b>TOTALODDS</b>")
    if c["total_verified"]:
        out.append(f"{c['total_odds']:.2f} – alle ledd kontrollert hos Norsk Tipping. Bekreft totalen i kupongen.")
    else:
        out.append(f"{c['total_odds']:.2f} – beregnet produkt av leddene. <b>Ikke verifisert hos Norsk Tipping.</b>")
    out.append("")
    out.append("<b>RISIKO</b>")
    if c["hit_est"] is not None:
        out.append(f"Grovt treffanslag: {pct(c['hit_est'])} (uvalidert modell, antar uavhengighet mellom kampene). "
                   f"Forventet verdi ut fra estimatene: {evp(c['ev_est'] or 0)}.")
    if band.speculative:
        out.append("Spekulativ bong med lav treffmulighet. Høy totalodds betyr ikke god pris.")
    others = db.all(
        """SELECT DISTINCT l2.coupon_id FROM coupon_legs l1 JOIN picks p1 ON p1.id=l1.pick_id
           JOIN coupon_legs l2 ON 1=1 JOIN picks p2 ON p2.id=l2.pick_id JOIN coupons c2 ON c2.id=l2.coupon_id
             AND c2.version=l2.version AND c2.superseded=0 AND c2.published_at IS NOT NULL
           WHERE l1.coupon_id=? AND l1.version=? AND l2.coupon_id<>? AND p1.fixture_id=p2.fixture_id""",
        (cid, c["version"], cid))
    if others:
        out.append("Deler kamp med: " + ", ".join(e(r["coupon_id"]) for r in sorted(others, key=lambda r: r["coupon_id"]))
                   + ". Ett resultat kan påvirke flere bonger.")
    out.append("")
    out.append("<b>FORBEHOLD</b>")
    out.append("Minste akseptable odds: " + ", ".join(f"ledd {i} ≥ {p['min_odds']:.2f}" for i, p in enumerate(legs, 1)))
    out.append("Trekkes ved vesentlige fravær i bekreftet oppstilling eller odds under minstegrensen.")
    if not c["total_verified"]:
        out.append("Ikke klar til innlevering før prisene er kontrollert i Oddsen.")
    return "\n".join(out)


def coupon_markup(cid: str, d: date) -> list:
    return [[["Full analyse", f"a:{cid}"], ["Kilder", f"s:{cid}"]],
            [["Kampstatus", f"k:{cid}"], ["Andre bonger", f"o:{d.isoformat()}"]]]


def pick_markup(pid: str) -> list:
    return [[["Full analyse", f"ap:{pid}"], ["Kilder", f"sp:{pid}"]]]


def full_pick_analysis(p: PickView, demo: bool) -> str:
    a = p.analysis
    f = a.get("fakta", {})
    sel = Selection.from_key(p["selection_key"])
    out = [_banner(demo) + f"🔍 <b>FULL ANALYSE · {e(p['id'])}</b>",
           f"<b>{e(p.fixture['home'])} – {e(p.fixture['away'])}</b> · {stamp(from_iso(p.fixture['kickoff']))}",
           f"{e(p.fixture['league_name'])}", "",
           f"Marked: {e(MARKET_NAMES.get(sel.market, sel.market))}",
           f"Valg: <b>{e(p['label'])}</b>",
           f"Odds: {odds_line(p)}", "",
           "<b>Sannsynlighet og pris</b>",
           f"Rå implisitt (1/odds): {pct(1 / p['odds'])}",
           f"Markedets marginfrie: {pct(p['market_q'])}",
           f"Modell (uvalidert): {pct(p['model_q'])}",
           f"Brukt estimat: {pct(p['final_q'])} ± {p['unc'] * 100:.1f} poeng",
           f"Forventet verdi: {evp(p['ev_point'])} (konservativt {evp(p['ev_cons'])})",
           f"Minste akseptable odds: {p['min_odds']:.2f}",
           f"Datakvalitet: {p['quality']:.2f} av 1 · Kategori: {e(tag_label(p.tags))}", ""]
    if "verdi" not in p.tags:
        out.append("<i>Ikke dokumentert verdi: estimatet ligger ikke tydelig over markedets terskel.</i>\n")
    out.append("<b>For</b>")
    out += [f"• {e(x)}" for x in a.get("for", [])] or ["• Ingen tydelige argumenter utover pris"]
    out.append("<b>Mot (sterkeste først)</b>")
    out += [f"• {e(x)}" for x in a.get("mot", [])]
    out.append("<b>Trekkes hvis</b>")
    out += [f"• {e(x)}" for x in a.get("trekk_hvis", [])]
    out.append("")
    for side in ("hjemme", "borte"):
        t = f.get(side)
        if not t:
            continue
        team = p.fixture["home"] if side == "hjemme" else p.fixture["away"]
        out.append(f"<b>{e(team)}</b>")
        out.append(f"Form siste 5: {e(t.get('siste5') or '–')} ({t.get('poeng5', '–')} p, målforskjell {t.get('mf5', 0):+d}, "
                   f"forventet {t.get('forventet_mf5', 0):+.1f})")
        out.append(f"Angrep {t.get('angrep_indeks')}× / forsvar {t.get('forsvar_indeks')}× ligasnitt "
                   f"(forsvar > 1 = slipper inn mer)")
        if t.get("xg_for") is not None:
            out.append(f"xG for/mot siste 10: {t['xg_for']} / {t['xg_mot']}")
        if t.get("hviledager") is not None:
            out.append(f"Hviledager: {t['hviledager']} · Datagrunnlag: {t.get('effektive_kamper')} effektive kamper")
    if f.get("tabell"):
        tb = f["tabell"]
        out.append(f"Tabell: {e(p.fixture['home'])} nr. {tb.get(p.fixture['home'])}, "
                   f"{e(p.fixture['away'])} nr. {tb.get(p.fixture['away'])} av {tb.get('lag_totalt')}")
    if f.get("innbyrdes"):
        out.append("Innbyrdes (supplerende, kan gjelde andre tropper): " + "; ".join(e(x) for x in f["innbyrdes"]))
    if f.get("fravær") is not None:
        fr = f["fravær"]
        out.append("Fravær: " + ("; ".join(f"{e(x['lag'])}: {e(x['spiller'])} ({e(x['status'].lower())}, {e(x['årsak'])})"
                                          for x in fr) if fr else "ingen registrerte"))
    out.append(f"Dommer: {e(f.get('dommer') or 'ikke oppgitt')} (dommerprofil ikke tilgjengelig)")
    out.append(f"<i>{e(a.get('taktikk', ''))}</i>")
    if a.get("datamangler"):
        out.append("Datamangler: " + "; ".join(e(x) for x in a["datamangler"]))
    out.append("")
    out.append(f"<b>Oppgjør</b>: {e(settlement_rule(sel))} Norsk Tippings spilleregler gjelder.")
    out.append(f"Modell: {e(p['model_version'])}")
    return "\n".join(out)


def sources_message(picks: list[PickView], provider_name: str, demo: bool) -> str:
    out = [_banner(demo) + "🔗 <b>KILDER</b>", ""]
    for p in picks:
        a = p.analysis
        out.append(f"<b>{e(p['id'])}</b> {e(p.fixture['home'])} – {e(p.fixture['away'])}")
        out.append(f"• Odds: {e(p['odds_source'])}, kontrollert {stamp(from_iso(p['odds_checked_at']))}")
        if p["ref_odds"]:
            out.append(f"• Referanse (median, {a.get('bookmakere', '?')} bookmakere): {p['ref_odds']:.2f}")
        out.append(f"• Kamp-ID hos {e(provider_name)}: <code>{e(p.fixture['id'])}</code>")
        out.append(f"• Fravær og historikk: {e(provider_name)}")
    out.append("")
    out.append("Norsk Tipping Oddsen: https://www.norsk-tipping.no/sport/oddsen")
    out.append("<i>Andre bookmakeres priser er sammenligningsgrunnlag og aldri Norsk Tipping-odds.</i>")
    return "\n".join(out)


def match_status(picks: list[PickView], last_check: str | None, delay_note: str, demo: bool) -> str:
    out = [_banner(demo) + "⚽ <b>KAMPSTATUS</b>", f"Siste datakontroll: {e(last_check or 'ingen ennå')}", ""]
    seen = set()
    for p in picks:
        f = p.fixture
        if f["id"] not in seen:
            seen.add(f["id"])
            score = ""
            if f.get("live_json"):
                lj = json.loads(f["live_json"])
                if lj.get("home_goals") is not None:
                    score = f" {lj['home_goals']}–{lj['away_goals']}"
            el = f" {f['elapsed']}'" if f.get("elapsed") and f["status"] not in ("FT", "NS") else ""
            out.append(f"<b>{e(f['home'])} – {e(f['away'])}</b>{score} · {e(f['status'])}{el}")
        out.append(f"  {e(p['label'])}: {e(leg_state(p))}")
    if not picks:
        out.append("Ingen aktive spill.")
    out.append("")
    out.append(f"<i>{e(delay_note)}</i>")
    return "\n".join(out)


# ------------------------------------------------------------------ varsler

def lineup_msg(f: dict, lineups: list, new_absences: list[str], demo: bool) -> str:
    out = [_banner(demo) + "📋 <b>BEKREFTEDE LAGOPPSTILLINGER</b>",
           f"<b>{e(f['home'])} – {e(f['away'])}</b> · {hm(from_iso(f['kickoff']))}"]
    for l in lineups:
        out.append(f"{e(l['team'])} ({e(l.get('formation') or '?')}): {e(', '.join(l['start_xi'][:11]))}")
    if new_absences:
        out.append("")
        out.append("Merk: " + "; ".join(e(x) for x in new_absences))
    return "\n".join(out)


def change_msg(title: str, lines: list[str], demo: bool) -> str:
    return _banner(demo) + f"🔄 <b>VESENTLIG ENDRING</b>\n<b>{e(title)}</b>\n" + "\n".join(f"• {e(x)}" for x in lines)


def event_msg(f: dict, ev: dict, score: str, demo: bool) -> str:
    icon = {"Goal": "⚽", "Card": "🟥" if "Red" in ev.get("detail", "") else "🟨", "Var": "📺"}.get(ev["type"], "•")
    detail = {"Normal Goal": "Mål", "Own Goal": "Selvmål", "Penalty": "Straffemål", "Missed Penalty": "Straffebom",
              "Yellow Card": "Gult kort", "Red Card": "Rødt kort", "Second Yellow card": "Andre gule kort",
              "Goal cancelled": "Mål annullert (VAR)", "Penalty confirmed": "Straffe bekreftet (VAR)"}.get(
        ev["detail"], ev["detail"])
    who = f" – {e(ev['player'])}" if ev.get("player") else ""
    return (_banner(demo) + f"{icon} {ev.get('minute') or '?'}' {e(detail)}, {e(ev['team'])}{who}\n"
            f"{e(f['home'])} – {e(f['away'])}: {e(score)}")


def lost_msg(groups: list[tuple[str, str, list[str]]], demo: bool) -> str:
    out = [_banner(demo) + "❌ <b>BEKREFTET TAPT</b>"]
    for match, leg, coupons in groups:
        out.append(f"{e(match)}: {e(leg)} røk.")
        out.append("Berørte bonger: " + ", ".join(f"<code>{e(c)}</code>" for c in coupons))
    out.append("<i>Bekreftet ut fra offisielt sluttresultat. Norsk Tippings oppgjør er gjeldende.</i>")
    return "\n".join(out)


def settled_msg(cid: str, outcome: str, ret: float, demo: bool) -> str:
    label = {"WON": "✅ Vunnet", "LOST": "❌ Tapt", "VOID": "➖ Annullert", "PARTIAL": "🟡 Delvis"}.get(outcome, outcome)
    return _banner(demo) + f"{label}: <code>{e(cid)}</code> · retur per enhet {ret:.2f}"


def reanalysis_msg(found: int, reason: str, demo: bool) -> str:
    if not found:
        return _banner(demo) + f"🔎 <b>Ny analyse fullført — ingen nye spill oppfyller kravene</b>\nUtløst av: {e(reason)}"
    return (_banner(demo) + f"🔎 <b>Ny analyse fullført</b>\nUtløst av: {e(reason)}\n{found} nytt forslag følger. "
            "Samme grenser som i morges; ingen høyere oddsmål eller flere ledd.")


def new_coupon_header(demo: bool) -> str:
    return _banner(demo) + "🧾 <b>NYTT BONGFORSLAG</b> (ekstra runde, egen ID)"


def ops_msg(title: str, detail: str) -> str:
    return f"⚙️ <b>DRIFTSAVVIK</b>\n<b>{e(title)}</b>\n{e(detail)}"


def daily_report(d: date, s: dict, demo: bool) -> str:
    out = [_banner(demo) + f"📊 <b>DAGSRAPPORT | {e(nice_date(d)).upper()}</b>", ""]
    out.append(f"Enkeltspill: {s['singles']['n']} · V {s['singles']['won']} · T {s['singles']['lost']} · "
               f"A {s['singles']['void']} · uavklart {s['singles']['open']}")
    out.append(f"Bonger: {s['coupons']['n']} · V {s['coupons']['won']} · T {s['coupons']['lost']} · "
               f"uavklart {s['coupons']['open']}")
    out.append(f"Simulert flat innsats (1 enhet per forslag): netto {s['sim_net']:+.2f} enheter")
    if s.get("extra_round"):
        out.append(f"Ekstra runde: {e(s['extra_round'])}")
    if s.get("gaps"):
        out.append("Datamangler/avbrudd: " + "; ".join(e(x) for x in s["gaps"]))
    out.append("")
    out.append("<i>Én dag sier ingenting om kvalitet. Se /stats for samlet historikk.</i>")
    return "\n".join(out)


# ------------------------------------------------------------------ meny og veiledning

WELCOME = (
    f"👋 <b>Velkommen til {BOT_NAME}</b>\n\n"
    "Jeg analyserer dagens fotballkamper, foreslår enkeltspill og kombinasjoner tilpasset "
    "Norsk Tipping, og følger kampene automatisk.\n\n"
    "• Morgenbrief kl. 08:00 (kan endres)\n"
    "• Separate bonger i ulike oddsnivåer\n"
    "• Varsler ved oppstillinger, endringer og resultater\n\n"
    "Forslagene er analyser, ikke garantier. Du leverer selv eventuelle spill.\n\n"
    + RG_FOOTER
)

GUIDE = (
    "📌 <b>BRUKERVEILEDNING</b>\n\n"
    "<b>Daglig flyt</b>\n"
    "06:15 analyse · 08:00 morgenbrief · før avspark oppstillinger · under kamp overvåking · 23:30 dagsrapport.\n\n"
    "<b>Begreper</b>\n"
    "• <i>Høy treffmulighet</i>: sannsynlig utfall, ikke nødvendigvis god pris.\n"
    "• <i>God pris</i>: estimatet ligger over prisens terskel (usikkert, modellen er uvalidert).\n"
    "• <i>Høy odds</i>: stor gevinst ved treff, lav treffmulighet.\n"
    "• <i>Foreløpig</i>: NT-pris ikke kontrollert. <i>Kontrollert</i>: alle priser kontrollert i Oddsen.\n"
    "• <i>Virker avgjort</i>: kampdata tyder på utfallet, men ikke bekreftet. <i>Bekreftet</i>: etter sluttresultat.\n\n"
    "<b>Kommandoer</b>\n"
    "/today oversikt · /morning siste brief · /singles enkeltspill · /coupons alle bonger\n"
    "/odds20 · /odds50 · /odds100 bonger rundt nivået\n"
    "/active aktive · /status kampstatus · /updates endringer · /results resultater · /stats historikk\n"
    "/settings preferanser · /notifications varsler · /pause · /resume\n"
    "/placed &lt;ID&gt; &lt;innsats&gt; registrer eget spill (privat) · /budget budsjett\n\n"
    "<b>Grenser</b>\n"
    "Maks én ekstra analyse-runde per dag etter tap. Ingen økning av oddsmål, ledd eller innsats etter tap.\n\n"
    + RG_FOOTER
)

COMMANDS = [
    ("today", "Dagens oversikt"), ("morning", "Siste morgenbrief"), ("singles", "Enkeltspill"),
    ("coupons", "Alle dagens bonger"), ("odds20", "Bonger rundt odds 20"), ("odds50", "Bonger rundt odds 50"),
    ("odds100", "Bonger rundt odds 100"), ("active", "Aktive bonger"), ("status", "Kampstatus og datakontroll"),
    ("updates", "Endrede forutsetninger"), ("refresh", "Ny kontroll innenfor grensene"), ("results", "Resultater"),
    ("stats", "Samlet historikk"), ("settings", "Preferanser"), ("notifications", "Varslingsnivå"),
    ("pause", "Stopp tips og varsler"), ("resume", "Gjenoppta"), ("help", "Brukerveiledning"),
]

MAIN_MENU = [[["📅 I dag", "m:today"], ["🌅 Morgenbrief", "m:morning"]],
             [["🎯 Enkeltspill", "m:singles"], ["🧾 Bonger", "m:coupons"]],
             [["⚽ Kampstatus", "m:status"], ["📊 Historikk", "m:stats"]],
             [["⚙️ Innstillinger", "m:settings"]]]


def stats_message(s: dict, personal: dict | None, demo: bool) -> str:
    out = [_banner(demo) + "📊 <b>SAMLET HISTORIKK</b>", ""]
    for key, title in (("singles", "Enkeltspill"), ("coupons", "Bonger")):
        x = s[key]
        out.append(f"<b>{title}</b>: {x['n']} avgjort · V {x['won']} · T {x['lost']} · A {x['void']} · "
                   f"uavklart {x['open']}")
        if x["n"]:
            out.append(f"Treff {pct(x['hit'])} · simulert yield {evp(x['yield'])} · netto {x['net']:+.2f} enheter · "
                       f"største fall {x['max_dd']:.2f} enheter")
    if s.get("by_market"):
        out.append("")
        out.append("<b>Per marked (enkeltspill)</b>")
        for m, x in s["by_market"].items():
            out.append(f"• {e(m)}: {x['n']} · treff {pct(x['hit'])} · yield {evp(x['yield'])}")
    if s.get("by_band"):
        out.append("<b>Per oddskategori (bonger)</b>")
        for m, x in s["by_band"].items():
            out.append(f"• {e(m)}: {x['n']} · treff {pct(x['hit'])} · yield {evp(x['yield'])}")
    if s.get("clv") is not None:
        out.append(f"Snitt prisendring mot sluttodds (CLV): {evp(s['clv'])} (n={s['clv_n']})")
    out.append("")
    n = s["singles"]["n"]
    out.append(f"<i>Utvalg: {n} enkeltspill. " + ("Under 200 avgjorte spill er for lite til å konkludere om lønnsomhet."
               if n < 200 else "Resultater er fortsatt beheftet med varians.") +
               " Simulering = 1 enhet per publisert forslag; ikke faktisk innsats. Ledd som går igjen i flere bonger "
               "er ikke uavhengige bevis.</i>")
    if personal:
        out.append("")
        out.append("<b>Dine registrerte spill (privat)</b>")
        out.append(f"{personal['n']} spill · innsats {personal['stake']:.0f} · retur {personal['ret']:.0f} · "
                   f"netto {personal['net']:+.0f} · åpne {personal['open']}")
    return "\n".join(out)


def contains_banned(text: str) -> list[str]:
    low = text.lower()
    return [w for w in BANNED_WORDS if w in low]
