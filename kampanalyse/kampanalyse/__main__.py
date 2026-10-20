"""Kommandolinje.

  python -m kampanalyse run           Start boten (krever TELEGRAM_BOT_TOKEN og OWNER_TELEGRAM_ID)
  python -m kampanalyse demo          Simuler en hel dag offline med FIKTIVE data, skriv meldinger til terminal
  python -m kampanalyse selftest      Kontroller konfigurasjon, database, datakilder og Telegram
  python -m kampanalyse backtest F..  Tidsbasert modelltest på CSV-filer
  python -m kampanalyse healthcheck   Avslutt med kode 0 hvis motoren har kjørt siste 3 min (for Docker)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone

from .config import Config
from .db import DB
from .engine import Engine
from .timeutil import Clock, FixedClock, from_iso, hm, local_at


def build(cfg: Config, db: DB, clock: Clock | None = None) -> Engine:
    clock = clock or Clock()
    if cfg.data_provider == "demo":
        from .providers.demo import DemoProvider
        prov = DemoProvider(clock)
        nt = [prov]
    elif cfg.data_provider == "apifootball":
        from .providers.apifootball import APIFootball
        from .providers.norsktipping import ManualNT, OddsApiIoNT
        prov = APIFootball(cfg.apifootball_key, db, cfg.apifootball_daily_cap)
        nt = [ManualNT(db)]
        if cfg.oddsapiio_key:
            nt.append(OddsApiIoNT(cfg.oddsapiio_key, cfg.oddsapiio_nt_bookmaker))
    else:
        raise SystemExit(f"Ukjent DATA_PROVIDER: {cfg.data_provider}")
    return Engine(cfg, db, prov, nt, clock)


class PrintSender:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.n = 0

    async def send(self, chat_id, text, markup):
        self.n += 1
        plain = re.sub(r"<[^>]+>", "", text).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        stamp = hm(self.clock.now())
        print(f"\n────────── [{stamp}] til {chat_id} ──────────\n{plain}")
        if markup:
            print("  " + "  ".join(f"[{t}]" for row in markup for t, _ in row))
        return self.n

    async def pin(self, chat_id, mid):
        pass


async def demo(day: date | None) -> None:
    day = day or date.today()
    clock = FixedClock(local_at(day, datetime.strptime("06:00", "%H:%M").time()))
    cfg = Config()
    cfg.data_provider = "demo"
    cfg.owner_telegram_id = 1
    db = DB(":memory:")
    eng = build(cfg, db, clock)
    eng.ensure_owner()
    db.execute("UPDATE users SET notify_level='normal' WHERE chat_id=1")
    eng.sender = PrintSender(clock)
    end = local_at(day, datetime.strptime("23:40", "%H:%M").time())
    while clock.now() < end:
        await eng.tick()
        clock.advance(minutes=1)
    print(f"\n{eng.sender.n} meldinger sendt i simuleringen (fiktive data).")


async def selftest(cfg: Config) -> int:
    ok = True
    print(f"Datakilde: {cfg.data_provider} · tidssone {cfg.timezone} · brief {cfg.default_brief_time:%H:%M}")
    try:
        db = DB(cfg.db_path)
        db.kv_set("selftest", datetime.now(timezone.utc).isoformat())
        print(f"✓ Database skrivbar: {cfg.db_path}")
    except Exception as e:  # noqa: BLE001
        print(f"✗ Database: {e}")
        return 1
    eng = build(cfg, db)
    try:
        fx = await eng.provider.fixtures_on(eng.today())
        rel = [f for f in fx if f.league_id in cfg.leagues or cfg.demo]
        print(f"✓ Kamper i dag: {len(fx)} totalt, {len(rel)} i valgte ligaer")
        if rel:
            q = await eng.provider.odds(rel[0])
            books = {x.bookmaker for x in q}
            print(f"✓ Odds for {rel[0].home}–{rel[0].away}: {len(q)} priser fra {len(books)} bookmakere")
            for s in eng.nt_sources:
                nt = await s.nt_odds(rel[0])
                print(f"  NT-kilde «{s.name}»: {len(nt)} priser")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"✗ Datakilde: {e}")
    if cfg.telegram_token:
        try:
            from telegram import Bot
            async with Bot(cfg.telegram_token) as bot:
                me = await bot.get_me()
                print(f"✓ Telegram: @{me.username}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"✗ Telegram: {e}")
    else:
        print("– Telegram-token ikke satt")
    if not cfg.owner_telegram_id:
        print("– OWNER_TELEGRAM_ID ikke satt (ingen vil få tilgang)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="kampanalyse")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    dp = sub.add_parser("demo")
    dp.add_argument("--date", type=date.fromisoformat, default=None)
    sub.add_parser("selftest")
    sub.add_parser("healthcheck")
    bp = sub.add_parser("backtest")
    bp.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.cmd == "demo":
        logging.getLogger().setLevel(logging.WARNING)
        asyncio.run(demo(a.date))
        return
    if a.cmd == "backtest":
        from .backtest import main as bt
        bt(a.rest)
        return
    cfg = Config.from_env()
    if a.cmd == "selftest":
        sys.exit(asyncio.run(selftest(cfg)))
    if a.cmd == "healthcheck":
        db = DB(cfg.db_path)
        t = db.kv_get("last_tick")
        sys.exit(0 if t and datetime.now(timezone.utc) - from_iso(t) < timedelta(minutes=3) else 1)
    if a.cmd == "run":
        if not cfg.telegram_token or not cfg.owner_telegram_id:
            raise SystemExit("TELEGRAM_BOT_TOKEN og OWNER_TELEGRAM_ID må settes (se .env.example)")
        logging.getLogger("httpx").setLevel(logging.WARNING)
        from .bot import BotApp
        db = DB(cfg.db_path)
        BotApp(build(cfg, db), cfg.telegram_token).run()


if __name__ == "__main__":
    main()
