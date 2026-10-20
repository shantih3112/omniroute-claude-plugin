"""Telegram-laget (python-telegram-bot v22). Kun kommandoer, knapper og sending.

Tilgang: bare brukere i `users`-tabellen. Roller: owner > admin > reader.
Nye medlemmer legges KUN til av eier med /adduser (aldri automatisk).
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import date, datetime, timedelta, timezone

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from . import render, repo, stats
from .coupons import BAND_BY_CODE, BANDS
from .engine import Engine
from .timeutil import day_bounds_utc, from_iso, hm, local, stamp, to_iso

log = logging.getLogger(__name__)
ROLE_RANK = {"reader": 0, "admin": 1, "owner": 2}
MAX_LEN = 3900


def keyboard(markup: list | None) -> InlineKeyboardMarkup | None:
    if not markup:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row] for row in markup])


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """Del lange meldinger på avsnitt, så HTML-tagger ikke brytes midt i."""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for para in text.split("\n\n"):
        chunk = para if not cur else cur + "\n\n" + para
        if len(chunk) <= limit:
            cur = chunk
            continue
        if cur:
            parts.append(cur)
        while len(para) > limit:
            cut = para.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            parts.append(para[:cut])
            para = para[cut:].lstrip("\n")
        cur = para
    if cur:
        parts.append(cur)
    return parts


class TelegramSender:
    def __init__(self, bot):
        self.bot = bot

    async def send(self, chat_id: int, text: str, markup: list | None) -> int | None:
        parts = split_message(text)
        mid = None
        for i, part in enumerate(parts):
            for attempt in range(3):
                try:
                    m = await self.bot.send_message(chat_id, part, parse_mode=ParseMode.HTML,
                                                    reply_markup=keyboard(markup) if i == len(parts) - 1 else None,
                                                    disable_web_page_preview=True)
                    mid = m.message_id
                    break
                except RetryAfter as ex:
                    await asyncio.sleep(float(getattr(ex, "retry_after", 5)) + 1)
                except Forbidden:
                    raise
        return mid

    async def pin(self, chat_id: int, message_id: int) -> None:
        await self.bot.pin_chat_message(chat_id, message_id, disable_notification=True)


class BotApp:
    def __init__(self, engine: Engine, token: str):
        self.engine = engine
        self.db = engine.db
        self.app = Application.builder().token(token).post_init(self._post_init).build()
        self._register()
        self._loop_task: asyncio.Task | None = None

    # ------------------------------------------------------------ oppstart
    async def _post_init(self, app: Application) -> None:
        self.engine.sender = TelegramSender(app.bot)
        self.engine.ensure_owner()
        try:
            await app.bot.set_my_commands([BotCommand(c, d) for c, d in render.COMMANDS])
            await app.bot.set_my_description(render.BOT_DESCRIPTION)
            await app.bot.set_my_short_description(render.BOT_SHORT)
        except Exception as ex:  # noqa: BLE001
            log.warning("Kunne ikke sette botprofil: %s", ex)
        self._loop_task = asyncio.create_task(self._tick_loop())
        self.engine.ops(f"start:{to_iso(self.engine.now())}", "Boten er startet",
                        "Aktive bonger og planlagte jobber gjenopptas fra databasen.")

    async def _tick_loop(self) -> None:
        while True:
            try:
                await self.engine.tick()
                self.db.kv_set("last_tick", to_iso(self.engine.now()))
            except Exception:  # noqa: BLE001
                log.exception("tick feilet")
            await asyncio.sleep(30)

    def run(self) -> None:
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)

    # ------------------------------------------------------------ tilgang
    def user(self, chat_id: int) -> dict | None:
        r = self.db.one("SELECT * FROM users WHERE chat_id=?", (chat_id,))
        return dict(r) if r else None

    async def _deny(self, update: Update) -> None:
        cid = update.effective_chat.id
        msg = (f"Du har ikke tilgang til {render.BOT_NAME}.\nDin Telegram-ID: <code>{cid}</code>\n"
               "Eieren kan gi tilgang med /adduser.")
        if update.callback_query:
            await update.callback_query.answer("Ingen tilgang", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_html(msg)

    def _guard(self, min_role: str, fn):
        async def wrapped(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            u = self.user(update.effective_chat.id) if update.effective_chat else None
            if not u or ROLE_RANK[u["role"]] < ROLE_RANK[min_role]:
                return await self._deny(update)
            # Kun privat chat for personlige data; kanalpublisering går via outbox.
            return await fn(update, ctx, u)
        return wrapped

    def _register(self) -> None:
        a = self.app
        a.add_handler(CommandHandler("start", self.cmd_start))
        cmds = {
            "help": ("reader", self.cmd_help), "guide": ("reader", self.cmd_help), "menu": ("reader", self.cmd_menu),
            "today": ("reader", self.cmd_today), "morning": ("reader", self.cmd_morning),
            "singles": ("reader", self.cmd_singles), "coupons": ("reader", self.cmd_coupons),
            "odds20": ("reader", self.cmd_odds20), "odds50": ("reader", self.cmd_odds50),
            "odds100": ("reader", self.cmd_odds100), "active": ("reader", self.cmd_active),
            "status": ("reader", self.cmd_status), "updates": ("reader", self.cmd_updates),
            "results": ("reader", self.cmd_results), "stats": ("reader", self.cmd_stats),
            "settings": ("reader", self.cmd_settings), "notifications": ("reader", self.cmd_notifications),
            "pause": ("reader", self.cmd_pause), "resume": ("reader", self.cmd_resume),
            "budget": ("reader", self.cmd_budget), "placed": ("reader", self.cmd_placed),
            "refresh": ("admin", self.cmd_refresh), "ntodds": ("admin", self.cmd_ntodds),
            "health": ("admin", self.cmd_health),
            "adduser": ("owner", self.cmd_adduser), "removeuser": ("owner", self.cmd_removeuser),
            "users": ("owner", self.cmd_users),
        }
        for name, (role, fn) in cmds.items():
            a.add_handler(CommandHandler(name, self._guard(role, fn)))
        a.add_handler(CallbackQueryHandler(self._guard("reader", self.on_callback)))

    # ------------------------------------------------------------ svarhjelpere
    async def reply(self, update: Update, text: str, markup: list | None = None) -> None:
        parts = split_message(text)
        for i, p in enumerate(parts):
            kb = keyboard(markup) if i == len(parts) - 1 else None
            if update.callback_query and i == 0:
                await update.callback_query.message.reply_html(p, reply_markup=kb, disable_web_page_preview=True)
            else:
                await update.effective_message.reply_html(p, reply_markup=kb, disable_web_page_preview=True)

    def d(self) -> date:
        return self.engine.today()

    # ------------------------------------------------------------ kommandoer
    async def cmd_start(self, update: Update, ctx) -> None:
        u = self.user(update.effective_chat.id)
        if not u:
            return await self._deny(update)
        await update.effective_message.reply_html(render.WELCOME, reply_markup=keyboard(render.MAIN_MENU))

    async def cmd_help(self, update: Update, ctx, u) -> None:
        m = await update.effective_message.reply_html(render.GUIDE)
        try:
            await ctx.bot.pin_chat_message(update.effective_chat.id, m.message_id, disable_notification=True)
        except (BadRequest, Forbidden):
            pass

    async def cmd_menu(self, update: Update, ctx, u) -> None:
        await self.reply(update, f"<b>{render.BOT_NAME}</b> – hovedmeny", render.MAIN_MENU)

    async def cmd_today(self, update: Update, ctx, u) -> None:
        d = self.d()
        run = self.engine.latest_run(d)
        coupons = repo.coupons_for_date(self.db, d)
        picks = [p for p in repo.picks_for_date(self.db, d) if p["rank"] <= 50]
        out = [render._banner(self.engine.cfg.demo) + f"📅 <b>I DAG | {render.e(render.nice_date(d))}</b>", ""]
        if not run:
            out.append(f"Analysen starter kl. {self.engine.cfg.research_time:%H:%M}. Morgenbrief kl. {u['brief_time']}.")
        else:
            notes = json.loads(run["notes_json"] or "{}")
            out.append(f"Analyse: {render.e(run['status'])} · {notes.get('fixtures', 0)} kamper kartlagt")
            out.append(f"Publisert: {len(picks)} enkeltspill · {len(coupons)} bonger")
            open_c = [c for c in coupons if not c["outcome"]]
            out.append(f"Åpne bonger: {len(open_c)} · Avgjorte: {len(coupons) - len(open_c)}")
            extra = self.db.kv_get(f"extra_round:{d.isoformat()}")
            out.append("Ekstra runde: " + ("brukt" if extra else "ikke brukt"))
        await self.reply(update, "\n".join(out), render.MAIN_MENU)

    async def cmd_morning(self, update: Update, ctx, u) -> None:
        txt = self.db.kv_get(f"brief_text:{self.d().isoformat()}")
        if not txt:
            row = self.db.one("SELECT key FROM kv WHERE key LIKE 'brief_text:%' ORDER BY key DESC LIMIT 1")
            txt = self.db.kv_get(row["key"]) if row else None
            if txt:
                txt = "<i>Dagens morgenbrief er ikke publisert ennå. Viser forrige:</i>\n\n" + txt
        await self.reply(update, txt or "Ingen morgenbrief er publisert ennå.", render.brief_markup(self.d()))

    async def cmd_singles(self, update: Update, ctx, u) -> None:
        picks = [p for p in repo.picks_for_date(self.db, self.d()) if p["rank"] <= 50 and not p["withdrawn_at"]]
        leagues = json.loads(u["leagues_json"]) if u.get("leagues_json") else None
        if leagues:
            picks = [p for p in picks if p.fixture["league_id"] in leagues]
        if not picks:
            return await self.reply(update, "Ingen enkeltspill oppfyller kravene i dag.")
        blocks = [f"<b>{render.e(p['id'])}</b> · {render.e(render.tag_label(p.tags))}\n" + render.pick_block(p, i)
                  for i, p in enumerate(picks, 1)]
        kb = [[[f"Analyse {i}", f"ap:{p['id']}"] for i, p in enumerate(picks[j:j + 4], j + 1)]
              for j in range(0, min(len(picks), 8), 4)]
        await self.reply(update, render._banner(self.engine.cfg.demo) + "🎯 <b>DAGENS ENKELTSPILL</b>\n\n"
                         + "\n\n".join(blocks), kb)

    def _coupon_list(self, codes: set[str] | None = None) -> tuple[str, list]:
        cs = repo.coupons_for_date(self.db, self.d())
        if codes:
            cs = [c for c in cs if c["band"] in codes]
        if not cs:
            return "Ingen kvalifisert bong i denne kategorien i dag.", []
        lines, kb = [], []
        for c in cs:
            b = BAND_BY_CODE[c["band"]]
            st = render.STATUS_NO.get(c["status"], c["status"].lower())
            lines.append(f"• <code>{render.e(c['id'])}</code> {render.e(b.title)} · odds {c['total_odds']:.2f} · {st}"
                         + (" · spekulativ" if b.speculative else ""))
            kb.append([[f"Vis {c['id']}", f"c:{c['id']}"]])
        return render._banner(self.engine.cfg.demo) + "🧾 <b>BONGER</b>\n" + "\n".join(lines), kb

    async def cmd_coupons(self, update: Update, ctx, u) -> None:
        await self.reply(update, *self._coupon_list())

    async def cmd_odds20(self, update, ctx, u):
        await self.reply(update, *self._coupon_list({"C", "D"}))

    async def cmd_odds50(self, update, ctx, u):
        await self.reply(update, *self._coupon_list({"D", "E"}))

    async def cmd_odds100(self, update, ctx, u):
        await self.reply(update, *self._coupon_list({"F", "G"}))

    async def cmd_active(self, update: Update, ctx, u) -> None:
        rows = self.db.all("SELECT * FROM coupons WHERE superseded=0 AND published_at IS NOT NULL AND outcome IS NULL "
                           "ORDER BY id")
        if not rows:
            return await self.reply(update, "Ingen aktive bonger.")
        mine = {r["ref_id"] for r in self.db.all("SELECT ref_id FROM user_bets WHERE chat_id=?", (u["chat_id"],))}
        out = [render._banner(self.engine.cfg.demo) + "🟢 <b>AKTIVE BONGER</b>", ""]
        kb = []
        for c in rows:
            legs = repo.coupon_legs(self.db, c["id"], c["version"])
            done = sum(1 for l in legs if l["result"])
            mark = " · registrert innlevert av deg" if c["id"] in mine else " · kun publisert (ingen registrert innsats)"
            out.append(f"<code>{render.e(c['id'])}</code> · {done}/{len(legs)} ledd avgjort · odds {c['total_odds']:.2f}{mark}")
            for l in legs:
                out.append(f"  {render.e(l['label'])}: {render.e(render.leg_state(l))}")
            kb.append([[f"Kampstatus {c['id']}", f"k:{c['id']}"]])
        await self.reply(update, "\n".join(out), kb[:8])

    async def cmd_status(self, update: Update, ctx, u) -> None:
        picks = [repo.pick(self.db, r["id"]) for r in self.db.all(
            "SELECT p.id FROM picks p JOIN fixtures f ON f.id=p.fixture_id WHERE p.published_at IS NOT NULL "
            "AND p.withdrawn_at IS NULL AND f.local_date=? ORDER BY f.kickoff", (self.d().isoformat(),))]
        h = self.db.one("SELECT * FROM health WHERE source='livedata'")
        last = stamp(from_iso(h["last_ok"])) if h and h["last_ok"] else None
        txt = render.match_status(picks, last, self.engine.provider.delay_note, self.engine.cfg.demo)
        if h and h["outage_since"]:
            txt += f"\n\n⚠️ Livedata feiler siden {stamp(from_iso(h['outage_since']))}. Status kan være utdatert."
        await self.reply(update, txt)

    async def cmd_updates(self, update: Update, ctx, u) -> None:
        start, _ = day_bounds_utc(self.d())
        rows = self.db.all("SELECT * FROM changes WHERE ts>=? AND kind NOT IN ('opprettet') ORDER BY id DESC LIMIT 25",
                           (to_iso(start),))
        if not rows:
            return await self.reply(update, "Ingen endrede forutsetninger i dag.")
        names = {"trukket": "Trukket", "odds_oppdatert": "Odds oppdatert", "odds_observert": "Odds endret",
                 "ny_versjon": "Ny versjon", "avgjort": "Avgjort", "korrigert": "Korrigert",
                 "oppstilling_avvik": "Avvik i oppstilling", "trukket_før_publisering": "Ikke publisert",
                 "nt_kontrollert": "NT-pris kontrollert"}
        out = ["🔄 <b>ENDRINGER I DAG</b>", ""]
        for r in rows:
            det = r["detail"] or ""
            out.append(f"{hm(from_iso(r['ts']))} <code>{render.e(r['entity_id'])}</code> "
                       f"{render.e(names.get(r['kind'], r['kind']))}: {render.e(det[:160])}")
        await self.reply(update, "\n".join(out))

    async def cmd_refresh(self, update: Update, ctx, u) -> None:
        await self.reply(update, "Kontrollerer ferske priser for dagens åpne forslag …")
        changes = await self.engine.recheck_open()
        extra = self.db.kv_get(f"extra_round:{self.d().isoformat()}")
        msg = ("Ingen vesentlige endringer funnet." if not changes else "Endringer er sendt som eget varsel.")
        msg += ("\nDagens ekstra analyse-runde er brukt." if extra else
                "\nNye spill publiseres bare i den ene ekstra runden etter et bekreftet tap.")
        await self.reply(update, msg)

    async def cmd_results(self, update: Update, ctx, u) -> None:
        out = [render._banner(self.engine.cfg.demo) + "🏁 <b>RESULTATER</b>"]
        for d in (self.d(), self.d() - timedelta(days=1)):
            out.append(f"\n<b>{render.e(render.nice_date(d))}</b>")
            any_ = False
            for p in repo.picks_for_date(self.db, d):
                if p["result"] and p["rank"] <= 50:
                    any_ = True
                    out.append(f"• {render.e(p['label'])} @ {p['odds']:.2f}: {render.e(render.leg_state(p))}")
            for c in repo.coupons_for_date(self.db, d):
                if c["outcome"]:
                    any_ = True
                    out.append(f"• <code>{render.e(c['id'])}</code> ({c['total_odds']:.2f}): {render.e(c['outcome'])}")
            if not any_:
                out.append("Ingen avgjorte forslag.")
        await self.reply(update, "\n".join(out))

    async def cmd_stats(self, update: Update, ctx, u) -> None:
        s = stats.overall(self.db)
        await self.reply(update, render.stats_message(s, stats.personal(self.db, u["chat_id"]), self.engine.cfg.demo))

    # ------------------------------------------------------------ innstillinger
    def _settings_view(self, u: dict) -> tuple[str, list]:
        cats = json.loads(u["categories_json"]) if u.get("categories_json") else [b.code for b in BANDS]
        quiet = f"{u['quiet_start']}–{u['quiet_end']}" if u.get("quiet_start") else "av"
        txt = (f"⚙️ <b>INNSTILLINGER</b>\n\nMorgenbrief: {u['brief_time']}\nVarslingsnivå: {u['notify_level']}\n"
               f"Stilleperiode: {quiet}\nOddskategorier: {', '.join(cats)}\n"
               f"Ligaer: {'alle' if not u.get('leagues_json') else len(json.loads(u['leagues_json']))} valgt\n"
               f"Status: {'pauset' if u['paused'] else 'aktiv'}")
        kb = [[["07:00", "set:brief:07:00"], ["07:30", "set:brief:07:30"], ["08:00", "set:brief:08:00"],
               ["09:00", "set:brief:09:00"]],
              [["Stille 23–07", "set:quiet:23:00-07:00"], ["Stille 22–08", "set:quiet:22:00-08:00"],
               ["Stille av", "set:quiet:off"]],
              [[("✓ " if b.code in cats else "") + b.code, f"set:cat:{b.code}"] for b in BANDS],
              [["Varsler", "m:notifications"], ["Ligaer", "set:leagues"]]]
        return txt, kb

    async def cmd_settings(self, update: Update, ctx, u) -> None:
        await self.reply(update, *self._settings_view(u))

    async def cmd_notifications(self, update: Update, ctx, u) -> None:
        txt = ("🔔 <b>VARSLINGSNIVÅ</b>\n\n<b>Minimal</b>: morgenbrief, bonger, tap/gevinst, ny analyse, dagsrapport.\n"
               "<b>Normal</b>: + oppstillinger, vesentlige endringer, avspark, røde kort og VAR.\n"
               "<b>Detaljert</b>: + alle mål og gule kort.\n\nNåværende: " + u["notify_level"])
        kb = [[["Minimal", "set:notify:minimal"], ["Normal", "set:notify:normal"], ["Detaljert", "set:notify:detaljert"]]]
        await self.reply(update, txt, kb)

    async def cmd_pause(self, update: Update, ctx, u) -> None:
        self.db.execute("UPDATE users SET paused=1 WHERE chat_id=?", (u["chat_id"],))
        await self.reply(update, "⏸ Tips og varsler er stoppet. Bruk /resume for å gjenoppta.")

    async def cmd_resume(self, update: Update, ctx, u) -> None:
        self.db.execute("UPDATE users SET paused=0 WHERE chat_id=?", (u["chat_id"],))
        await self.reply(update, "▶️ Tjenesten er gjenopptatt.")

    # ------------------------------------------------------------ innsats (privat)
    async def cmd_budget(self, update: Update, ctx, u) -> None:
        args = ctx.args or []
        if len(args) != 2:
            cur = (f"Nå: månedsbudsjett {u['budget_month']:.0f}, daglig grense {u['daily_limit']:.0f}."
                   if u.get("budget_month") else "Ikke satt.")
            return await self.reply(update, "Bruk: /budget &lt;underholdningsbudsjett per måned&gt; &lt;maks daglig "
                                    "eksponering&gt;\nEksempel: /budget 1000 100\n\nBoten foreslår aldri innsatsbeløp. "
                                    "Grensen gjelder alle bonger samlet, også etter tap.\n" + cur)
        try:
            month, daily = float(args[0].replace(",", ".")), float(args[1].replace(",", "."))
        except ValueError:
            return await self.reply(update, "Ugyldige tall.")
        if daily <= 0 or month <= 0 or daily > month:
            return await self.reply(update, "Daglig grense må være positiv og ikke større enn månedsbudsjettet.")
        self.db.execute("UPDATE users SET budget_month=?, daily_limit=? WHERE chat_id=?", (month, daily, u["chat_id"]))
        await self.reply(update, f"Budsjett lagret: {month:.0f} per måned, maks {daily:.0f} per dag. Kun synlig for deg.")

    async def cmd_placed(self, update: Update, ctx, u) -> None:
        args = ctx.args or []
        if not u.get("daily_limit"):
            return await self.reply(update, "Sett først et underholdningsbudsjett med /budget.")
        if len(args) < 2:
            return await self.reply(update, "Bruk: /placed &lt;ID&gt; &lt;innsats&gt; [faktisk NT-odds]\n"
                                    "Registrerer et spill du selv har levert. Privat for deg.")
        ref = args[0].upper()
        try:
            stake = float(args[1].replace(",", "."))
        except ValueError:
            return await self.reply(update, "Ugyldig innsats.")
        if ref.startswith("K-"):
            c = repo.coupon_latest(self.db, ref)
            if not c:
                return await self.reply(update, "Fant ikke bongen.")
            odds = c["total_odds"]
            fixtures = {l.fixture["id"] for l in repo.coupon_legs(self.db, ref, c["version"])}
        else:
            p = repo.pick(self.db, ref)
            if not p:
                return await self.reply(update, "Fant ikke forslaget.")
            odds = p["odds"]
            fixtures = {p.fixture["id"]}
        if len(args) > 2:
            try:
                odds = float(args[2].replace(",", "."))
            except ValueError:
                pass
        d = self.d().isoformat()
        today = self.db.all("SELECT * FROM user_bets WHERE chat_id=? AND local_date=?", (u["chat_id"], d))
        used = sum(b["stake"] for b in today)
        if used + stake > u["daily_limit"]:
            return await self.reply(update, f"Avvist: dagens registrerte eksponering {used:.0f} + {stake:.0f} overstiger "
                                    f"din daglige grense {u['daily_limit']:.0f}. Grensen gjelder også etter tap.")
        overlap = []
        for b in today:
            other = set()
            if b["ref_id"].startswith("K-"):
                oc = repo.coupon_latest(self.db, b["ref_id"])
                other = {l.fixture["id"] for l in repo.coupon_legs(self.db, b["ref_id"], oc["version"])} if oc else set()
            else:
                op = repo.pick(self.db, b["ref_id"])
                other = {op.fixture["id"]} if op else set()
            if other & fixtures:
                overlap.append(b["ref_id"])
        self.db.execute("INSERT INTO user_bets(chat_id,ref_id,stake,odds,placed_at,local_date) VALUES(?,?,?,?,?,?)",
                        (u["chat_id"], ref, stake, odds, to_iso(self.engine.now()), d))
        msg = f"Registrert: {ref}, innsats {stake:.0f} @ {odds:.2f}. Dagens eksponering: {used + stake:.0f} av {u['daily_limit']:.0f}."
        if overlap:
            msg += "\n⚠️ Deler kamp med dine spill " + ", ".join(overlap) + " – samlet risiko er høyere enn det ser ut."
        await self.reply(update, msg)

    # ------------------------------------------------------------ admin
    async def cmd_ntodds(self, update: Update, ctx, u) -> None:
        args = ctx.args or []
        if len(args) != 2:
            return await self.reply(update, "Bruk: /ntodds &lt;spill-ID&gt; &lt;odds&gt;\nLegg inn prisen du har kontrollert "
                                    "selv i Oddsen. Eksempel: /ntodds E-261020-03 1,85")
        p = repo.pick(self.db, args[0].upper())
        if not p:
            return await self.reply(update, "Fant ikke spillet.")
        try:
            odds = float(args[1].replace(",", "."))
        except ValueError:
            return await self.reply(update, "Ugyldig odds.")
        if odds <= 1.0:
            return await self.reply(update, "Odds må være over 1,00.")
        now = to_iso(self.engine.now())
        self.db.execute("INSERT INTO nt_odds_manual(fixture_id,selection_key,odds,entered_by,entered_at) VALUES(?,?,?,?,?)",
                        (p["fixture_id"], p["selection_key"], odds, u["chat_id"], now))
        ev = (1 - p["p_void"]) * (p["final_q"] * odds - 1)
        self.db.execute("UPDATE picks SET odds=?, odds_kind='NT_KONTROLLERT', odds_source=?, odds_checked_at=?, ev_point=? "
                        "WHERE id=?", (odds, "Norsk Tipping (manuelt kontrollert)", now, ev, p["id"]))
        self.db.log_change(now, "pick", p["id"], "nt_kontrollert", {"fra": p["odds"], "til": odds, "av": u["chat_id"]})
        msg = [f"NT-pris lagret for {p['id']}: {odds:.2f} (før {p['odds']:.2f})."]
        if odds < p["min_odds"]:
            msg.append(f"⚠️ Under minste akseptable odds {p['min_odds']:.2f} – forslaget bør trekkes.")
        for c in self.engine._coupons_with_fixture(p["fixture_id"]):
            legs = repo.coupon_legs(self.db, c["id"], c["version"])
            if p["id"] not in {l["id"] for l in legs}:
                continue
            total = round(math.prod(l["odds"] for l in legs), 2)
            verified = all(l["odds_kind"] == "NT_KONTROLLERT" for l in legs)
            status = "KONTROLLERT" if verified and c["status"] == "FORELØPIG" else None
            v = repo.supersede_coupon(self.db, c["id"], status, self.engine.now(), f"NT-pris kontrollert for {p['id']}",
                                      total, verified)
            msg.append(f"{c['id']} → versjon {v}, totalodds {total:.2f}" + (" (alle ledd kontrollert)" if verified else ""))
        await self.reply(update, "\n".join(msg))

    async def cmd_health(self, update: Update, ctx, u) -> None:
        rows = self.db.all("SELECT * FROM health")
        last_tick = self.db.kv_get("last_tick")
        calls = self.db.kv_get(f"apif_calls:{datetime.now(timezone.utc).date().isoformat()}") or "0"
        out = ["🩺 <b>DRIFT</b>", f"Siste tick: {stamp(from_iso(last_tick)) if last_tick else 'ukjent'}",
               f"Datakilde: {render.e(self.engine.provider.name)} · API-kall i dag: {calls}"]
        for r in rows:
            out.append(f"• {render.e(r['source'])}: OK {stamp(from_iso(r['last_ok'])) if r['last_ok'] else '–'}"
                       + (f" · avbrudd siden {stamp(from_iso(r['outage_since']))}" if r["outage_since"] else ""))
        pend = self.db.one("SELECT COUNT(*) n FROM outbox WHERE status='pending'")["n"]
        failed = self.db.one("SELECT COUNT(*) n FROM outbox WHERE status='failed'")["n"]
        out.append(f"Utsendingskø: {pend} venter · {failed} feilet")
        await self.reply(update, "\n".join(out))

    async def cmd_adduser(self, update: Update, ctx, u) -> None:
        args = ctx.args or []
        if len(args) != 2 or args[1] not in ("reader", "admin"):
            return await self.reply(update, "Bruk: /adduser &lt;telegram-id&gt; reader|admin")
        try:
            cid = int(args[0])
        except ValueError:
            return await self.reply(update, "Ugyldig ID.")
        self.db.execute("INSERT INTO users(chat_id,name,role,brief_time,created_at) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(chat_id) DO UPDATE SET role=excluded.role",
                        (cid, None, args[1], self.engine.cfg.default_brief_time.strftime("%H:%M"),
                         to_iso(self.engine.now())))
        await self.reply(update, f"Bruker {cid} lagt til som {args[1]}. Brukeren må sende /start til boten.")

    async def cmd_removeuser(self, update: Update, ctx, u) -> None:
        args = ctx.args or []
        if len(args) != 1 or not args[0].lstrip("-").isdigit() or int(args[0]) == u["chat_id"]:
            return await self.reply(update, "Bruk: /removeuser &lt;telegram-id&gt; (ikke deg selv)")
        self.db.execute("DELETE FROM users WHERE chat_id=? AND role<>'owner'", (int(args[0]),))
        await self.reply(update, "Tilgang fjernet. Brukerens private spillhistorikk er beholdt, men ikke synlig for andre.")

    async def cmd_users(self, update: Update, ctx, u) -> None:
        rows = self.db.all("SELECT chat_id, role, paused FROM users ORDER BY role")
        await self.reply(update, "👥 <b>BRUKERE</b>\n" + "\n".join(
            f"• <code>{r['chat_id']}</code> {r['role']}{' (pauset)' if r['paused'] else ''}" for r in rows))

    # ------------------------------------------------------------ knapper
    async def on_callback(self, update: Update, ctx, u) -> None:
        q = update.callback_query
        data = q.data or ""
        await q.answer()
        demo = self.engine.cfg.demo
        kind, _, arg = data.partition(":")
        if kind == "m":
            fn = {"today": self.cmd_today, "morning": self.cmd_morning, "singles": self.cmd_singles,
                  "coupons": self.cmd_coupons, "status": self.cmd_status, "stats": self.cmd_stats,
                  "settings": self.cmd_settings, "notifications": self.cmd_notifications}.get(arg)
            if fn:
                ctx.args = []
                return await fn(update, ctx, u)
        if kind == "c":
            c = repo.coupon_latest(self.db, arg)
            if c:
                d = from_iso(c["published_at"]) if c["published_at"] else self.engine.now()
                return await self.reply(update, render.coupon_message(self.db, arg, demo),
                                        render.coupon_markup(arg, local(d).date()))
        if kind == "a":
            c = repo.coupon_latest(self.db, arg)
            if c:
                legs = repo.coupon_legs(self.db, arg, c["version"])
                return await self.reply(update, "\n\n".join(render.full_pick_analysis(p, demo) for p in legs))
        if kind == "ap":
            p = repo.pick(self.db, arg)
            if p:
                return await self.reply(update, render.full_pick_analysis(p, demo))
        if kind == "s":
            c = repo.coupon_latest(self.db, arg)
            if c:
                return await self.reply(update, render.sources_message(repo.coupon_legs(self.db, arg, c["version"]),
                                                                       self.engine.provider.name, demo))
        if kind == "sp":
            p = repo.pick(self.db, arg)
            if p:
                return await self.reply(update, render.sources_message([p], self.engine.provider.name, demo))
        if kind == "k":
            c = repo.coupon_latest(self.db, arg)
            if c:
                h = self.db.one("SELECT last_ok FROM health WHERE source='livedata'")
                return await self.reply(update, render.match_status(
                    repo.coupon_legs(self.db, arg, c["version"]),
                    stamp(from_iso(h["last_ok"])) if h and h["last_ok"] else None, self.engine.provider.delay_note, demo))
        if kind == "o":
            return await self.reply(update, *self._coupon_list())
        if kind == "set":
            return await self._on_setting(update, u, arg)
        await q.message.reply_text("Denne knappen er ikke lenger gyldig.")

    async def _on_setting(self, update: Update, u: dict, arg: str) -> None:
        key, _, val = arg.partition(":")
        cid = u["chat_id"]
        if key == "brief":
            self.db.execute("UPDATE users SET brief_time=? WHERE chat_id=?", (val, cid))
        elif key == "quiet":
            if val == "off":
                self.db.execute("UPDATE users SET quiet_start=NULL, quiet_end=NULL WHERE chat_id=?", (cid,))
            else:
                s, e = val.split("-")
                self.db.execute("UPDATE users SET quiet_start=?, quiet_end=? WHERE chat_id=?", (s, e, cid))
        elif key == "notify" and val in ("minimal", "normal", "detaljert"):
            self.db.execute("UPDATE users SET notify_level=? WHERE chat_id=?", (val, cid))
        elif key == "cat":
            cats = json.loads(u["categories_json"]) if u.get("categories_json") else [b.code for b in BANDS]
            cats = [c for c in cats if c != val] if val in cats else sorted(cats + [val])
            self.db.execute("UPDATE users SET categories_json=? WHERE chat_id=?", (json.dumps(cats), cid))
        elif key == "leagues":
            chosen = json.loads(u["leagues_json"]) if u.get("leagues_json") else []
            kb = [[[("✓ " if lid in chosen else "") + name, f"set:lg:{lid}"]] for lid, name in
                  list(self.engine.cfg.leagues.items())[:15]]
            kb.append([["Alle ligaer", "set:lg:all"]])
            return await self.reply(update, "Velg ligaer for enkeltspill-listen (ingen valgt = alle):", kb)
        elif key == "lg":
            if val == "all":
                self.db.execute("UPDATE users SET leagues_json=NULL WHERE chat_id=?", (cid,))
            else:
                chosen = json.loads(u["leagues_json"]) if u.get("leagues_json") else []
                lid = int(val)
                chosen = [x for x in chosen if x != lid] if lid in chosen else chosen + [lid]
                self.db.execute("UPDATE users SET leagues_json=? WHERE chat_id=?",
                                (json.dumps(chosen) if chosen else None, cid))
        u2 = self.user(cid)
        await self.reply(update, *self._settings_view(u2))
