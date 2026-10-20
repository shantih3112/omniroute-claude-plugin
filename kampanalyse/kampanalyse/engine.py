"""Motoren. All tidsstyrt logikk går gjennom `tick()`, som kalles hvert ~30. sekund.

`tick()` er idempotent og leser all tilstand fra databasen. Derfor:
- Omstart midt på dagen gjenopptar overvåking av aktive bonger automatisk.
- Hver planlagt hendelse har en unik nøkkel (kv_claim / outbox.dedupe_key), så den
  kjøres og sendes bare én gang – også etter omstart.
"""
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, time, timedelta

from . import render, repo, stats
from .analysis import Analyzer, Candidate
from .config import Config
from .coupons import BAND_BY_CODE, BANDS, build_all
from .db import DB
from .markets import MatchStats, Result, Selection, live_state, payout_factor, settle
from .providers.base import FINAL_STATUSES, LIVE_STATUSES, VOID_STATUSES, ProviderError
from .timeutil import Clock, day_bounds_utc, from_iso, hm, local_at, local_date, stamp, to_iso

log = logging.getLogger(__name__)

LEVELS = {"minimal": 0, "normal": 1, "detaljert": 2}
KIND_LEVEL = {"brief": 0, "coupon": 0, "report": 0, "lost": 0, "settled": 0, "newround": 0,
              "lineup": 1, "change": 1, "status": 1, "event": 2}
MAX_SINGLES = 10


class Engine:
    def __init__(self, cfg: Config, db: DB, provider, nt_sources: list, clock: Clock | None = None):
        self.cfg = cfg
        self.db = db
        self.provider = provider
        self.nt_sources = nt_sources
        self.clock = clock or Clock()
        self.analyzer = Analyzer(cfg, provider, nt_sources)
        self.sender = None  # settes av bot-laget (eller testene)

    # ------------------------------------------------------------ hjelpere
    def now(self) -> datetime:
        return self.clock.now()

    def today(self) -> date:
        return local_date(self.now())

    def users(self, active_only: bool = True) -> list[dict]:
        rows = self.db.all("SELECT * FROM users" + (" WHERE paused=0" if active_only else ""))
        return [dict(r) for r in rows]

    def ensure_owner(self) -> None:
        if self.cfg.owner_telegram_id:
            self.db.execute("INSERT OR IGNORE INTO users(chat_id,name,role,brief_time,created_at) VALUES(?,?,?,?,?)",
                            (self.cfg.owner_telegram_id, "Eier", "owner",
                             self.cfg.default_brief_time.strftime("%H:%M"), to_iso(self.now())))

    def notify(self, kind: str, key: str, text: str, markup: list | None = None, roles: tuple = (),
               only: int | None = None, pin: bool = False, band: str | None = None) -> int:
        """Legg melding i kø for alle relevante brukere. Respekterer pause, nivå og stilleperiode."""
        n = 0
        for u in self.users():
            if only is not None and u["chat_id"] != only:
                continue
            if roles and u["role"] not in roles:
                continue
            if kind in KIND_LEVEL and KIND_LEVEL[kind] > LEVELS.get(u["notify_level"], 1):
                continue
            cats = json.loads(u["categories_json"]) if u.get("categories_json") else None
            if kind == "coupon" and band and cats is not None and band not in cats:
                continue
            nb = repo.in_quiet(u, self.now())
            if repo.enqueue(self.db, f"{key}:{u['chat_id']}", u["chat_id"], text, markup, self.now(), nb, pin):
                n += 1
        if self.cfg.publish_channel_id and kind in ("brief", "coupon", "report", "lost", "newround"):
            repo.enqueue(self.db, f"{key}:channel", self.cfg.publish_channel_id, text, markup, self.now())
        return n

    def ops(self, key: str, title: str, detail: str) -> None:
        log.warning("DRIFTSAVVIK %s: %s", title, detail)
        self.notify("ops", f"ops:{key}", render.ops_msg(title, detail), roles=("owner", "admin"))

    def health_ok(self, source: str) -> None:
        r = self.db.one("SELECT outage_since FROM health WHERE source=?", (source,))
        now = to_iso(self.now())
        if r and r["outage_since"]:
            since = from_iso(r["outage_since"])
            self.ops(f"recovered:{source}:{r['outage_since']}", f"{source} virker igjen",
                     f"Avbrudd {stamp(since)}–{hm(self.now())}. Hendelser i perioden ble ikke fanget i sanntid; "
                     "status er hentet på nytt nå.")
        self.db.execute("""INSERT INTO health(source,last_ok,outage_since) VALUES(?,?,NULL)
                           ON CONFLICT(source) DO UPDATE SET last_ok=excluded.last_ok, outage_since=NULL""",
                        (source, now))

    def health_err(self, source: str, err: str) -> None:
        now = to_iso(self.now())
        self.db.execute("""INSERT INTO health(source,last_error,last_error_at,outage_since) VALUES(?,?,?,?)
                           ON CONFLICT(source) DO UPDATE SET last_error=excluded.last_error,
                           last_error_at=excluded.last_error_at,
                           outage_since=COALESCE(health.outage_since, excluded.outage_since)""",
                        (source, err, now, now))

    # ------------------------------------------------------------ tick
    async def tick(self) -> None:
        now = self.now()
        d = self.today()
        steps = [
            ("research", self._maybe_research(d)),
            ("brief", self._maybe_briefs(d)),
            ("lineups", self._lineups()),
            ("closing", self._closing_odds()),
            ("live", self._live()),
            ("settle", self._settle_coupons()),
            ("report", self._maybe_report(d)),
            ("stale", self._stale_check()),
        ]
        for name, coro in steps:
            try:
                await coro
            except Exception as ex:  # noqa: BLE001 – ett steg skal aldri stoppe de andre
                log.exception("tick-steg %s feilet", name)
                self.ops(f"tick:{name}:{now:%Y%m%d%H}", f"Feil i steg «{name}»", str(ex)[:300])
        if self.sender:
            await self.flush_outbox()

    # ------------------------------------------------------------ research
    async def _maybe_research(self, d: date) -> None:
        if self.now() < local_at(d, self.cfg.research_time):
            return
        if not self.db.kv_claim(f"run:morning:{d.isoformat()}", to_iso(self.now())):
            return
        await self.run_research(d, "morning")

    async def run_research(self, d: date, kind: str, max_band: str | None = None, max_legs: int | None = None,
                           reason: str = "") -> dict:
        """Kjør full analyse. kind: morning | extra."""
        now = self.now()
        run_id = repo.new_run(self.db, kind, d, now, self.cfg.model_version)
        problems: list[str] = []
        try:
            fixtures = await self.provider.fixtures_on(d)
            self.health_ok("kampdata")
        except ProviderError as ex:
            self.health_err("kampdata", str(ex))
            repo.finish_run(self.db, run_id, "failed", self.now(), {"problems": [str(ex)]})
            self.ops(f"research:{run_id}", "Analysen kunne ikke hente dagens kamper", str(ex))
            return {"run_id": run_id, "status": "failed"}
        allowed = set(self.cfg.leagues) | ({9001} if self.cfg.demo else set())
        lead = timedelta(minutes=45 if kind == "extra" else 30)
        relevant = [f for f in fixtures if f.league_id in allowed]
        upcoming = [f for f in relevant if f.status in ("NS", "TBD") and f.kickoff > now + lead]
        for f in upcoming:
            repo.upsert_fixture(self.db, f, now)
        ctxs, probs = await self.analyzer.load_contexts(upcoming, d)
        problems += probs
        screened = [c for c in ctxs if c.quality >= self.cfg.min_quality]
        for c in ctxs:
            if c.quality < self.cfg.min_quality:
                problems.append(f"{c.fixture.home}–{c.fixture.away} utelatt: datakvalitet {c.quality:.2f}")
        cands: list[Candidate] = []
        for c in screened:
            cands += self.analyzer.evaluate(c, now)
        short = self.analyzer.shortlist(cands)
        bands = BANDS
        if max_band:
            bands = [b for b in BANDS if b.code <= max_band]
            if max_legs:
                bands = [replace(b, max_legs=min(b.max_legs, max_legs)) for b in bands]
        blocked = set()
        if kind == "extra":
            # Ikke lag en ny bong av ledd som allerede ligger i aktive bonger (ingen falsk risikospredning)
            for r in self.db.all("""SELECT p.fixture_id, p.selection_key FROM coupons c
                                    JOIN coupon_legs l ON l.coupon_id=c.id AND l.version=c.version
                                    JOIN picks p ON p.id=l.pick_id
                                    WHERE c.superseded=0 AND c.published_at IS NOT NULL AND c.outcome IS NULL"""):
                blocked.add((r["fixture_id"], Selection.from_key(r["selection_key"])))
        drafts, empty = build_all(short, bands, blocked)
        if kind == "extra":
            drafts = drafts[:1]  # Én ny bong i ekstrarunden
        # Lagre enkeltspill (rangert) og alle ledd som brukes i bonger
        singles = [c for c in short if "verdi" in c.tags or "høy_treff" in c.tags][:MAX_SINGLES if kind == "morning" else 0]
        ids: dict[int, str] = {}
        for i, c in enumerate(singles, 1):
            ids[id(c)] = repo.save_pick(self.db, run_id, c, i, self.cfg.model_version, d)
        k = 100
        for dr in drafts:
            for leg in dr.legs:
                if id(leg) not in ids:
                    k += 1
                    ids[id(leg)] = repo.save_pick(self.db, run_id, leg, k, self.cfg.model_version, d)
        coupon_ids = [repo.save_coupon(self.db, run_id, d, dr, [ids[id(l)] for l in dr.legs], now) for dr in drafts]
        notes = {"problems": problems, "fixtures": len(relevant), "screened": len(screened),
                 "candidates": len(cands), "shortlist": len(short), "empty_bands": empty, "reason": reason,
                 "checked_at": to_iso(now)}
        repo.finish_run(self.db, run_id, "ok", self.now(), notes)
        log.info("Analyse %s ferdig: %d kamper, %d kandidater, %d bonger", kind, len(upcoming), len(cands), len(drafts))
        return {"run_id": run_id, "status": "ok", "coupons": coupon_ids, "singles": [ids[id(c)] for c in singles]}

    def latest_run(self, d: date, kind: str = "morning") -> dict | None:
        r = self.db.one("SELECT * FROM runs WHERE local_date=? AND kind=? ORDER BY id DESC LIMIT 1",
                        (d.isoformat(), kind))
        return dict(r) if r else None

    # ------------------------------------------------------------ kontroll før publisering
    async def prepublish_check(self, run_id: int) -> list[str]:
        """Hent ferske priser og kontroller kamp, tid, marked og minste odds før publisering."""
        now = self.now()
        changes: list[str] = []
        picks = self.db.all("SELECT * FROM picks WHERE run_id=? AND withdrawn_at IS NULL", (run_id,))
        by_fx: dict[str, list] = defaultdict(list)
        for p in picks:
            by_fx[p["fixture_id"]].append(p)
        for fid, ps in by_fx.items():
            f = self.db.one("SELECT * FROM fixtures WHERE id=?", (fid,))
            fx = repo.fixture_from_row(f)
            if fx.kickoff <= now + timedelta(minutes=10):
                for p in ps:
                    self._withdraw(p["id"], "Kampen starter før publisering")
                continue
            try:
                quotes = await self.provider.odds(fx)
                nt = []
                for s in self.nt_sources:
                    try:
                        nt += await s.nt_odds(fx)
                    except Exception:  # noqa: BLE001
                        pass
            except ProviderError as ex:
                changes.append(f"Kunne ikke kontrollere odds for {fx.home}–{fx.away}: {ex}")
                continue
            for p in ps:
                sel = Selection.from_key(p["selection_key"])
                if p["odds_kind"] == "REFERANSE":
                    vals = sorted(q.odds for q in quotes if q.selection == sel and not q.is_nt)
                    new = vals[len(vals) // 2] if vals else None
                else:
                    cands = [q for q in nt if q.selection == sel]
                    cands.sort(key=lambda q: (q.nt_verified, q.checked_at), reverse=True)
                    new = cands[0].odds if cands else None
                if new is None:
                    self._withdraw(p["id"], "Markedet finnes ikke lenger hos kilden")
                    changes.append(f"{p['label']} trukket: markedet mangler")
                elif new < p["min_odds"]:
                    self._withdraw(p["id"], f"Odds {new:.2f} under minste akseptable {p['min_odds']:.2f}")
                    changes.append(f"{p['label']} trukket: odds {new:.2f} < {p['min_odds']:.2f}")
                else:
                    if abs(new - p["odds"]) >= 0.01:
                        self.db.log_change(to_iso(now), "pick", p["id"], "odds_oppdatert",
                                           {"fra": p["odds"], "til": new})
                    ev = (1 - p["p_void"]) * (p["final_q"] * new - 1)
                    self.db.execute("UPDATE picks SET odds=?, odds_checked_at=?, ev_point=? WHERE id=?",
                                    (new, to_iso(now), ev, p["id"]))
        # Bonger med trukne ledd publiseres ikke; totalodds oppdateres for resten
        for c in self.db.all("SELECT * FROM coupons WHERE run_id=? AND superseded=0", (run_id,)):
            legs = repo.coupon_legs(self.db, c["id"], c["version"])
            if any(l["withdrawn_at"] for l in legs):
                self.db.execute("UPDATE coupons SET status='TRUKKET' WHERE id=? AND version=?", (c["id"], c["version"]))
                self.db.log_change(to_iso(now), "coupon", c["id"], "trukket_før_publisering")
                changes.append(f"{c['id']} ikke publisert: ett eller flere ledd trukket")
                continue
            tot = round(math.prod(l["odds"] for l in legs), 2)
            band = BAND_BY_CODE[c["band"]]
            if not (band.lo <= tot <= band.hi):
                self.db.execute("UPDATE coupons SET status='TRUKKET' WHERE id=? AND version=?", (c["id"], c["version"]))
                changes.append(f"{c['id']} ikke publisert: totalodds {tot:.2f} utenfor kategorien")
                continue
            self.db.execute("UPDATE coupons SET total_odds=?, odds_checked_at=? WHERE id=? AND version=?",
                            (tot, to_iso(now), c["id"], c["version"]))
        return changes

    async def recheck_open(self) -> list[str]:
        """/refresh: kontroller ferske priser for publiserte, ikke startede forslag. Publiserer ingen nye spill."""
        now = self.now()
        changes: list[str] = []
        rows = self.db.all("""SELECT p.* FROM picks p JOIN fixtures f ON f.id=p.fixture_id
                              WHERE p.published_at IS NOT NULL AND p.withdrawn_at IS NULL AND p.result IS NULL
                              AND f.kickoff > ?""", (to_iso(now),))
        by_fx: dict[str, list] = defaultdict(list)
        for p in rows:
            by_fx[p["fixture_id"]].append(p)
        for fid, ps in by_fx.items():
            fx = repo.fixture_from_row(self.db.one("SELECT * FROM fixtures WHERE id=?", (fid,)))
            try:
                quotes = await self.provider.odds(fx)
                nt = []
                for s in self.nt_sources:
                    try:
                        nt += await s.nt_odds(fx)
                    except Exception:  # noqa: BLE001
                        pass
            except ProviderError as ex:
                changes.append(f"{fx.home}–{fx.away}: odds kunne ikke hentes ({ex})")
                continue
            for p in ps:
                sel = Selection.from_key(p["selection_key"])
                pool = [q.odds for q in nt if q.selection == sel] if p["odds_kind"] != "REFERANSE" else \
                    sorted(q.odds for q in quotes if q.selection == sel and not q.is_nt)
                new = (pool[len(pool) // 2] if p["odds_kind"] == "REFERANSE" else pool[0]) if pool else None
                if new is None:
                    changes.append(f"{p['id']} {p['label']}: markedet finnes ikke lenger hos kilden")
                elif new < p["min_odds"]:
                    self._withdraw(p["id"], f"Odds {new:.2f} under minste akseptable {p['min_odds']:.2f}")
                    changes.append(f"{p['id']} {p['label']}: odds {new:.2f} under minstegrensen "
                                   f"{p['min_odds']:.2f} – anbefales trukket")
                elif abs(new - p["odds"]) >= 0.05:
                    changes.append(f"{p['id']} {p['label']}: odds {p['odds']:.2f} → {new:.2f} (over minstegrensen)")
                    self.db.log_change(to_iso(now), "pick", p["id"], "odds_observert", {"fra": p["odds"], "til": new})
        if changes:
            self.notify("change", f"refresh:{to_iso(now)}", render.change_msg("Ny kontroll av dagens forslag", changes,
                                                                             self.cfg.demo))
        return changes

    def _withdraw(self, pid: str, reason: str) -> None:
        self.db.execute("UPDATE picks SET withdrawn_at=?, withdrawn_reason=? WHERE id=? AND withdrawn_at IS NULL",
                        (to_iso(self.now()), reason, pid))
        self.db.log_change(to_iso(self.now()), "pick", pid, "trukket", reason)

    async def publish_run(self, run_id: int, d: date) -> None:
        """Merk forslag publisert (én gang) etter kontroll."""
        if not self.db.kv_claim(f"published:{run_id}", to_iso(self.now())):
            return
        changes = await self.prepublish_check(run_id)
        now = to_iso(self.now())
        self.db.execute("""UPDATE picks SET published_at=? WHERE run_id=? AND withdrawn_at IS NULL""", (now, run_id))
        self.db.execute("""UPDATE coupons SET published_at=? WHERE run_id=? AND superseded=0 AND status<>'TRUKKET'""",
                        (now, run_id))
        self.db.kv_set(f"prepublish_changes:{run_id}", json.dumps(changes, ensure_ascii=False))

    # ------------------------------------------------------------ morgenbrief
    async def _maybe_briefs(self, d: date) -> None:
        run = self.latest_run(d)
        now = self.now()
        for u in self.users():
            bt = time.fromisoformat(u["brief_time"])
            due = local_at(d, bt)
            if now < due or now > local_at(d, time(23, 0)):
                continue
            if self.db.one("SELECT 1 FROM outbox WHERE dedupe_key=?", (f"brief:{d.isoformat()}:{u['chat_id']}",)):
                continue
            if not run or run["status"] == "running":
                if now > due + timedelta(minutes=30):
                    self.ops(f"late:{d.isoformat()}", "Morgenbrief forsinket",
                             "Analysen er ikke ferdig 30 min etter planlagt tid.")
                continue
            if run["status"] == "failed":
                self.notify("brief", f"brief:{d.isoformat()}", render._banner(self.cfg.demo) +
                            f"🌅 <b>MORGENBRIEF | {render.e(render.nice_date(d)).upper()}</b>\n\n"
                            "Analysen feilet i dag fordi data ikke kunne hentes. Ingen forslag publiseres "
                            "uten kontrollerte data.\n\n" + render.RG_FOOTER, only=u["chat_id"])
                continue
            await self.publish_run(run["id"], d)
            self.send_brief(d, run, only=u["chat_id"])

    def brief_text(self, d: date, run: dict) -> str:
        notes = json.loads(run["notes_json"] or "{}")
        picks = [p for p in repo.picks_for_date(self.db, d) if p["rank"] <= 50 and p["run_id"] == run["id"]]
        coupons = [c for c in repo.coupons_for_date(self.db, d) if c["run_id"] == run["id"]]
        watch = []
        fx_ids = {p.fixture["id"] for p in picks} | {l.fixture["id"] for c in coupons
                                                     for l in repo.coupon_legs(self.db, c["id"], c["version"])}
        for fid in fx_ids:
            f = self.db.one("SELECT home,away,kickoff FROM fixtures WHERE id=?", (fid,))
            watch.append(f"Oppstilling {f['home']}–{f['away']} ca. {hm(from_iso(f['kickoff']) - timedelta(minutes=60))}")
        watch.sort(key=lambda s: s[-5:])
        changes = json.loads(self.db.kv_get(f"prepublish_changes:{run['id']}") or "[]")
        watch += changes[:2]
        if any(p["odds_kind"] != "NT_KONTROLLERT" for p in picks):
            watch.append("NT-priser er ikke manuelt kontrollert – sjekk i Oddsen før innlevering")
        first = min((from_iso(self.db.one("SELECT kickoff FROM fixtures WHERE id=?", (fid,))["kickoff"]) for fid in fx_ids),
                    default=None)
        nxt = (f"Oppstillinger fra ca. {hm(first - timedelta(minutes=60))}, deretter automatisk kampoppfølging."
               if first else "Ingen kamper å følge i dag. Dagsrapport kl. " + self.cfg.report_time.strftime("%H:%M"))
        checked = max((from_iso(p["odds_checked_at"]) for p in picks), default=from_iso(notes.get("checked_at")) if notes.get("checked_at") else None)
        return render.morning_brief(d, self.now(), checked, picks, coupons, notes.get("empty_bands", []),
                                    notes.get("fixtures", 0), notes.get("screened", 0), notes.get("problems", []),
                                    watch, nxt, self.cfg.demo, self.db)

    def send_brief(self, d: date, run: dict, only: int | None = None) -> None:
        text = self.brief_text(d, run)
        self.db.kv_set(f"brief_text:{d.isoformat()}", text)
        self.notify("brief", f"brief:{d.isoformat()}", text, render.brief_markup(d), only=only)
        for c in [c for c in repo.coupons_for_date(self.db, d) if c["run_id"] == run["id"]]:
            self.notify("coupon", f"coupon:{c['id']}:v{c['version']}", render.coupon_message(self.db, c["id"], self.cfg.demo),
                        render.coupon_markup(c["id"], d), only=only, band=c["band"])

    # ------------------------------------------------------------ fulgte kamper
    def tracked_fixtures(self) -> list[dict]:
        """Kamper i publiserte forslag som ikke er endelig avgjort (inkl. korreksjonsvindu)."""
        horizon = to_iso(self.now() - timedelta(hours=self.cfg.correction_check_hours))
        rows = self.db.all(
            """SELECT DISTINCT f.* FROM fixtures f JOIN picks p ON p.fixture_id=f.id
               WHERE p.published_at IS NOT NULL AND p.withdrawn_at IS NULL
                 AND (f.final_confirmed_at IS NULL OR f.final_confirmed_at > ?)""", (horizon,))
        return [dict(r) for r in rows]

    async def _lineups(self) -> None:
        now = self.now()
        for f in self.tracked_fixtures():
            ko = from_iso(f["kickoff"])
            if f["lineups_at"] or not (ko - timedelta(minutes=70) <= now <= ko + timedelta(minutes=5)):
                continue
            last = self.db.kv_get(f"lineup_poll:{f['id']}")
            if last and now - from_iso(last) < timedelta(minutes=5):
                continue
            self.db.kv_set(f"lineup_poll:{f['id']}", to_iso(now))
            fx = repo.fixture_from_row(f)
            try:
                lus = await self.provider.lineups(fx)
            except ProviderError as ex:
                self.health_err("oppstillinger", str(ex))
                continue
            if not lus:
                continue
            data = [{"team": l.team, "formation": l.formation, "start_xi": l.start_xi} for l in lus]
            self.db.execute("UPDATE fixtures SET lineups_json=?, lineups_at=? WHERE id=?",
                            (json.dumps(data, ensure_ascii=False), to_iso(now), f["id"]))
            notes = []
            # Sammenlign med fraværslisten fra analysen
            picks = self.db.all("SELECT * FROM picks WHERE fixture_id=? AND published_at IS NOT NULL AND withdrawn_at IS NULL",
                                (f["id"],))
            known = set()
            for p in picks:
                for a in json.loads(p["analysis_json"]).get("fakta", {}).get("fravær", []) or []:
                    known.add(a["spiller"])
            starters = {n for l in lus for n in l.start_xi}
            back = [n for n in known if n in starters]
            if back:
                notes.append("Spiller oppført som fravær starter likevel: " + ", ".join(back))
            try:
                fresh = await self.provider.absences(fx)
            except ProviderError:
                fresh = None
            if fresh:
                new = [f"{a.player} ({a.team})" for a in fresh if a.kind == "Ute" and a.player not in known]
                if new:
                    notes.append("Nye fravær siden analysen: " + ", ".join(new))
            self.notify("lineup", f"lineup:{f['id']}", render.lineup_msg(f, data, notes, self.cfg.demo))
            if notes:
                self.notify("change", f"change:lineup:{f['id']}", render.change_msg(
                    f"{f['home']} – {f['away']}", notes + ["Vurder om forslag i denne kampen fortsatt holder. "
                                                           "Modellen justerer ikke automatisk for enkeltspillere."],
                    self.cfg.demo))
                for p in picks:
                    self.db.log_change(to_iso(now), "pick", p["id"], "oppstilling_avvik", notes)

    async def _closing_odds(self) -> None:
        now = self.now()
        for f in self.tracked_fixtures():
            ko = from_iso(f["kickoff"])
            if not (ko - timedelta(minutes=10) <= now <= ko):
                continue
            picks = self.db.all("SELECT * FROM picks WHERE fixture_id=? AND published_at IS NOT NULL AND closing_odds IS NULL",
                                (f["id"],))
            if not picks:
                continue
            try:
                quotes = await self.provider.odds(repo.fixture_from_row(f))
            except ProviderError:
                continue
            for p in picks:
                sel = Selection.from_key(p["selection_key"])
                vals = sorted(q.odds for q in quotes if q.selection == sel and not q.is_nt)
                if vals:
                    self.db.execute("UPDATE picks SET closing_odds=?, closing_checked_at=? WHERE id=?",
                                    (vals[len(vals) // 2], to_iso(now), p["id"]))

    # ------------------------------------------------------------ live
    async def _live(self) -> None:
        now = self.now()
        due = []
        for f in self.tracked_fixtures():
            ko = from_iso(f["kickoff"])
            if now < ko - timedelta(minutes=2):
                continue
            # Etter bekreftelse: sjekk korrigeringer sjeldnere
            interval = timedelta(minutes=30) if f["final_confirmed_at"] else timedelta(seconds=self.cfg.live_poll_seconds)
            if f["live_at"] and now - from_iso(f["live_at"]) < interval - timedelta(seconds=2):
                continue
            due.append(f)
        if not due:
            return
        try:
            snaps = await self.provider.live([f["id"] for f in due])
            self.health_ok("livedata")
        except ProviderError as ex:
            self.health_err("livedata", str(ex))
            return
        by_id = {s.fixture_id: s for s in snaps}
        for f in due:
            s = by_id.get(f["id"])
            if s:
                self._apply_snapshot(f, s)

    def _apply_snapshot(self, f: dict, s) -> None:
        now = self.now()
        prev_status = f["status"]
        live = {"home_goals": s.home_goals, "away_goals": s.away_goals, "ft_home": s.ft_home, "ft_away": s.ft_away,
                "ht_home": s.ht_home, "ht_away": s.ht_away, "cards": s.cards, "corners": s.corners}
        self.db.execute("UPDATE fixtures SET status=?, elapsed=?, live_json=?, live_at=? WHERE id=?",
                        (s.status, s.elapsed, json.dumps(live), to_iso(now), f["id"]))
        score = f"{s.home_goals if s.home_goals is not None else '-'}–{s.away_goals if s.away_goals is not None else '-'}"

        # Hendelser (dedupe per hendelse). Annullerte mål meldes eksplisitt.
        for ev in s.events:
            if ev.type not in ("Goal", "Card", "Var"):
                continue
            # Mål og gule kort: detaljert nivå. Røde kort og VAR-avgjørelser: normalt nivå.
            kind = "status" if (ev.type == "Var" or "Red" in ev.detail) else "event"
            cur = self.db.execute("INSERT OR IGNORE INTO live_events(fixture_id,event_key,seen_at,minute,type,detail,team,player) "
                                  "VALUES(?,?,?,?,?,?,?,?)", (f["id"], ev.key(), to_iso(now), ev.minute, ev.type,
                                                              ev.detail, ev.team, ev.player))
            if cur.rowcount == 1:
                self.notify(kind, f"event:{f['id']}:{ev.key()}", render.event_msg(f, ev.__dict__, score, self.cfg.demo))
        if prev_status in ("NS", "TBD") and s.status in LIVE_STATUSES:
            self.notify("status", f"kickoff:{f['id']}", render._banner(self.cfg.demo) +
                        f"⚽ Avspark: {render.e(f['home'])} – {render.e(f['away'])}")
            for c in self._coupons_with_fixture(f["id"]):
                if c["status"] in ("FORELØPIG", "KONTROLLERT"):
                    self.db.execute("UPDATE coupons SET status='STARTET' WHERE id=? AND version=?", (c["id"], c["version"]))

        picks = self.db.all("SELECT * FROM picks WHERE fixture_id=? AND published_at IS NOT NULL AND withdrawn_at IS NULL",
                            (f["id"],))
        if s.status in VOID_STATUSES:
            for p in picks:
                if p["live_state"] != "UAVKLART":
                    self.db.execute("UPDATE picks SET live_state='UAVKLART' WHERE id=?", (p["id"],))
            self.notify("change", f"void:{f['id']}:{s.status}", render.change_msg(
                f"{f['home']} – {f['away']}", [f"Kampstatus {s.status} (utsatt/avbrutt/avlyst).",
                                               "Leddene står som uavklart. Norsk Tippings regler avgjør om de annulleres."],
                self.cfg.demo))
            return

        if s.status in LIVE_STATUSES and s.home_goals is not None:
            st = MatchStats(s.home_goals, s.away_goals, s.ht_home, s.ht_away, s.cards, s.corners)
            for p in picks:
                if p["result"]:
                    continue
                ls = live_state(Selection.from_key(p["selection_key"]), st,
                                first_half_over=s.status not in ("1H",)).value
                if ls != p["live_state"]:
                    self.db.execute("UPDATE picks SET live_state=? WHERE id=?", (ls, p["id"]))

        if s.status in FINAL_STATUSES and s.ft_home is not None:
            final = {"h": s.ft_home, "a": s.ft_away, "hth": s.ht_home, "hta": s.ht_away, "cards": s.cards,
                     "corners": s.corners}
            fj = json.dumps(final, sort_keys=True)
            if f["final_confirmed_at"]:
                if fj != f["final_json"]:
                    self._correction(f, final, fj)
                return
            if fj != f["final_json"]:
                # Nytt eller endret sluttresultat: start bekreftelsesvinduet på nytt
                self.db.execute("UPDATE fixtures SET final_json=?, final_first_seen=? WHERE id=?",
                                (fj, to_iso(now), f["id"]))
                for p in picks:
                    if not p["result"]:
                        self.db.execute("UPDATE picks SET live_state='AVSLUTTET' WHERE id=?", (p["id"],))
                return
            if now - from_iso(f["final_first_seen"]) >= timedelta(minutes=self.cfg.settle_confirm_minutes):
                self._confirm_final(f, final)

    def _stats_from_final(self, final: dict) -> MatchStats:
        return MatchStats(final["h"], final["a"], final.get("hth"), final.get("hta"), final.get("cards"), final.get("corners"))

    def _confirm_final(self, f: dict, final: dict) -> None:
        now = self.now()
        self.db.execute("UPDATE fixtures SET final_confirmed_at=? WHERE id=?", (to_iso(now), f["id"]))
        st = self._stats_from_final(final)
        for p in self.db.all("SELECT * FROM picks WHERE fixture_id=? AND result IS NULL", (f["id"],)):
            r = settle(Selection.from_key(p["selection_key"]), st)
            if r is None:
                self.db.execute("UPDATE picks SET live_state='UAVKLART' WHERE id=?", (p["id"],))
                continue
            self.db.execute("UPDATE picks SET result=?, result_confirmed_at=?, live_state=NULL WHERE id=?",
                            (r.value, to_iso(now), p["id"]))
            self.db.log_change(to_iso(now), "pick", p["id"], "avgjort", {"resultat": r.value, "sluttresultat": final})

    def _correction(self, f: dict, final: dict, fj: str) -> None:
        now = self.now()
        old = json.loads(f["final_json"])
        self.db.execute("UPDATE fixtures SET final_json=?, corrected_at=? WHERE id=?", (fj, to_iso(now), f["id"]))
        st = self._stats_from_final(final)
        changed = []
        for p in self.db.all("SELECT * FROM picks WHERE fixture_id=?", (f["id"],)):
            r = settle(Selection.from_key(p["selection_key"]), st)
            if r and r.value != p["result"]:
                self.db.execute("UPDATE picks SET result=?, result_confirmed_at=? WHERE id=?", (r.value, to_iso(now), p["id"]))
                self.db.log_change(to_iso(now), "pick", p["id"], "korrigert", {"fra": p["result"], "til": r.value})
                changed.append(f"{p['label']}: {p['result']} → {r.value}")
        for c in self._coupons_with_fixture(f["id"]):
            self.db.execute("UPDATE coupons SET outcome=NULL, settled_at=NULL, status='STARTET' WHERE id=? AND version=?",
                            (c["id"], c["version"]))
        self.notify("change", f"correction:{f['id']}:{fj}", render.change_msg(
            f"Korrigert resultat: {f['home']} – {f['away']}",
            [f"Fra {old['h']}–{old['a']} til {final['h']}–{final['a']}."] + changed +
            ["Berørte bonger er vurdert på nytt."], self.cfg.demo))

    def _coupons_with_fixture(self, fid: str) -> list[dict]:
        rows = self.db.all("""SELECT DISTINCT c.* FROM coupons c JOIN coupon_legs l ON l.coupon_id=c.id AND l.version=c.version
                              JOIN picks p ON p.id=l.pick_id WHERE p.fixture_id=? AND c.superseded=0
                              AND c.published_at IS NOT NULL""", (fid,))
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ oppgjør av bonger
    async def _settle_coupons(self) -> None:
        now = self.now()
        rows = self.db.all("SELECT * FROM coupons WHERE superseded=0 AND published_at IS NOT NULL AND outcome IS NULL")
        newly_lost: list[tuple[dict, dict]] = []
        for c in rows:
            c = dict(c)
            legs = repo.coupon_legs(self.db, c["id"], c["version"])
            out = stats.coupon_outcome(legs)
            if out is None:
                continue
            ret = stats.coupon_return(legs) or 0.0
            self.db.execute("UPDATE coupons SET outcome=?, status='AVGJORT', settled_at=? WHERE id=? AND version=?",
                            (out, to_iso(now), c["id"], c["version"]))
            self.db.log_change(to_iso(now), "coupon", c["id"], "avgjort", {"utfall": out, "retur": ret})
            if out == "LOST":
                lost_leg = next(l for l in legs if l["result"] == "LOST")
                newly_lost.append((c, lost_leg))
            else:
                self.notify("settled", f"settled:{c['id']}:{out}", render.settled_msg(c["id"], out, ret, self.cfg.demo))
        self._settle_user_bets()
        if not newly_lost:
            return
        # Samle varsler: én melding per kamp som ødela bonger
        groups: dict[str, tuple[str, str, list[str]]] = {}
        for c, leg in newly_lost:
            key = leg.fixture["id"]
            if key not in groups:
                groups[key] = (f"{leg.fixture['home']} – {leg.fixture['away']}", leg["label"], [])
            groups[key][2].append(c["id"])
        gkey = "|".join(sorted(c["id"] for c, _ in newly_lost))
        self.notify("lost", f"lost:{gkey}", render.lost_msg(list(groups.values()), self.cfg.demo))
        await self.maybe_reanalyse([c for c, _ in newly_lost], "Bekreftet tapt: " + ", ".join(c["id"] for c, _ in newly_lost))

    def _settle_user_bets(self) -> None:
        for b in self.db.all("SELECT * FROM user_bets WHERE returned IS NULL"):
            ref = b["ref_id"]
            if ref.startswith("K-"):
                c = repo.coupon_latest(self.db, ref)
                if not c:
                    continue
                legs = repo.coupon_legs(self.db, ref, c["version"])
                ret = stats.coupon_return(legs)
                if ret is None:
                    continue
                factor = ret / c["total_odds"] * b["odds"] if c["total_odds"] and ret > 0 else ret
            else:
                p = repo.pick(self.db, ref)
                if not p or not p["result"]:
                    continue
                factor = payout_factor(Result(p["result"]), b["odds"])
            self.db.execute("UPDATE user_bets SET returned=?, settled_at=? WHERE id=?",
                            (round(b["stake"] * factor, 2), to_iso(self.now()), b["id"]))

    async def maybe_reanalyse(self, lost: list[dict], reason: str) -> dict:
        """Maks én ekstra publiseringsrunde per dag. Ingen høyere oddsmål eller flere ledd."""
        d = self.today()
        if self.cfg.max_extra_rounds_per_day < 1:
            return {"status": "disabled"}
        if not self.db.kv_claim(f"extra_round:{d.isoformat()}", reason):
            return {"status": "limit"}
        max_band = min(c["band"] for c in lost)
        max_legs = min(len(repo.coupon_legs(self.db, c["id"], c["version"])) for c in lost)
        res = await self.run_research(d, "extra", max_band=max_band, max_legs=max_legs, reason=reason)
        if res["status"] != "ok":
            self.notify("newround", f"newround:{d.isoformat()}", render.reanalysis_msg(0, reason, self.cfg.demo))
            return res
        await self.publish_run(res["run_id"], d)
        published = [c for c in repo.coupons_for_date(self.db, d) if c["run_id"] == res["run_id"]]
        self.notify("newround", f"newround:{d.isoformat()}", render.reanalysis_msg(len(published), reason, self.cfg.demo))
        for c in published:
            self.notify("coupon", f"coupon:{c['id']}:v{c['version']}",
                        render.new_coupon_header(self.cfg.demo) + "\n\n" + render.coupon_message(self.db, c["id"], self.cfg.demo),
                        render.coupon_markup(c["id"], d), band=c["band"])
        res["published"] = [c["id"] for c in published]
        return res

    # ------------------------------------------------------------ rapport og drift
    async def _maybe_report(self, d: date) -> None:
        if self.now() < local_at(d, self.cfg.report_time):
            return
        if not self.db.kv_claim(f"report:{d.isoformat()}", to_iso(self.now())):
            return
        s = stats.overall(self.db, since=d, until=d)
        extra = self.db.kv_get(f"extra_round:{d.isoformat()}")
        s["extra_round"] = extra
        gaps = [f"{r['source']}: siste feil {stamp(from_iso(r['last_error_at']))}" for r in
                self.db.all("SELECT * FROM health WHERE last_error_at >= ?", (to_iso(day_bounds_utc(d)[0]),))]
        s["gaps"] = gaps
        self.notify("report", f"report:{d.isoformat()}", render.daily_report(d, s, self.cfg.demo))

    async def _stale_check(self) -> None:
        now = self.now()
        live = [f for f in self.tracked_fixtures() if f["status"] in LIVE_STATUSES]
        if not live:
            return
        r = self.db.one("SELECT * FROM health WHERE source='livedata'")
        last = from_iso(r["last_ok"]) if r and r["last_ok"] else None
        if last is None or now - last > timedelta(minutes=self.cfg.stale_data_alert_minutes):
            since = r["outage_since"] if r and r["outage_since"] else to_iso(now)
            self.ops(f"stale:{since}", "Livedata er ikke oppdatert",
                     f"Siste vellykkede henting: {stamp(last) if last else 'aldri'}. "
                     f"Overvåkingen av {len(live)} pågående kamp(er) virker ikke nå. Status vises som sist kjent.")

    # ------------------------------------------------------------ utsending
    async def flush_outbox(self, limit: int = 30) -> int:
        now = to_iso(self.now())
        rows = self.db.all("""SELECT * FROM outbox WHERE status='pending' AND attempts<5
                              AND (not_before IS NULL OR not_before<=?) ORDER BY id LIMIT ?""", (now, limit))
        sent = 0
        for r in rows:
            try:
                mid = await self.sender.send(r["chat_id"], r["text"], json.loads(r["markup_json"]) if r["markup_json"] else None)
                self.db.execute("UPDATE outbox SET status='sent', sent_at=?, tg_message_id=?, attempts=attempts+1 WHERE id=?",
                                (to_iso(self.now()), mid, r["id"]))
                if r["pin"] and mid:
                    try:
                        await self.sender.pin(r["chat_id"], mid)
                    except Exception:  # noqa: BLE001
                        pass
                sent += 1
            except Exception as ex:  # noqa: BLE001
                log.warning("Sending feilet (%s): %s", r["dedupe_key"], ex)
                self.db.execute("UPDATE outbox SET attempts=attempts+1, last_error=?, status=CASE WHEN attempts+1>=5 "
                                "THEN 'failed' ELSE 'pending' END WHERE id=?", (str(ex)[:300], r["id"]))
        return sent
