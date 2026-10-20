"""Telegram-tilgangskontroll, knapper, innsatsgrenser, API-Football-parsing og backtest."""
import json
from datetime import date, time

import httpx

from kampanalyse import repo
from kampanalyse.backtest import Row, run as backtest_run
from kampanalyse.bot import BotApp, split_message
from kampanalyse.db import DB
from kampanalyse.markets import Selection
from kampanalyse.providers.apifootball import APIFootball, parse_bet
from kampanalyse.timeutil import local_at
from tests.conftest import fake_update, make_engine, run_until



async def _bot_with_day():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(8, 1)))
    bot = BotApp(eng, "123456:TEST-TOKEN-NOT-REAL")
    eng.db.execute("INSERT INTO users(chat_id,role,brief_time,created_at) VALUES(5,'reader','08:00','x')")
    return bot, eng, clock


async def test_access_control():
    bot, eng, _ = await _bot_with_day()
    # Ukjent bruker
    upd, ctx, rep = fake_update(999)
    await bot._guard("reader", bot.cmd_today)(upd, ctx)
    assert "ikke tilgang" in rep[0]
    # Leser kan ikke bruke admin-kommandoer
    upd, ctx, rep = fake_update(5, args=["E-261020-01", "2.0"])
    await bot._guard("admin", bot.cmd_ntodds)(upd, ctx)
    assert "ikke tilgang" in rep[0]
    upd, ctx, rep = fake_update(5, args=["777", "admin"])
    await bot._guard("owner", bot.cmd_adduser)(upd, ctx)
    assert "ikke tilgang" in rep[0]
    assert not eng.db.one("SELECT 1 FROM users WHERE chat_id=777")
    # Ukjent bruker kan ikke trykke knapper
    upd, ctx, rep = fake_update(999, data="c:K-261020-B1")
    await bot._guard("reader", bot.on_callback)(upd, ctx)
    assert rep[0][0] == "answer"


async def test_all_coupon_buttons_work_for_reader():
    bot, eng, _ = await _bot_with_day()
    coupons = repo.coupons_for_date(eng.db, date(2026, 10, 20))
    assert coupons
    cid = coupons[0]["id"]
    for data in [f"c:{cid}", f"a:{cid}", f"s:{cid}", f"k:{cid}", "o:2026-10-20", "m:today", "m:singles",
                 "m:coupons", "m:status", "m:stats", "m:settings", "m:notifications", "m:morning"]:
        upd, ctx, rep = fake_update(5, data=data)
        await bot._guard("reader", bot.on_callback)(upd, ctx)
        texts = [r for r in rep if isinstance(r, str)]
        assert texts and "ikke lenger gyldig" not in texts[-1], data
    p = repo.picks_for_date(eng.db, date(2026, 10, 20))[0]
    for data in [f"ap:{p['id']}", f"sp:{p['id']}"]:
        upd, ctx, rep = fake_update(5, data=data)
        await bot._guard("reader", bot.on_callback)(upd, ctx)
        assert any(isinstance(r, str) and len(r) > 50 for r in rep)
    upd, ctx, rep = fake_update(5, data="xyz:1")
    await bot._guard("reader", bot.on_callback)(upd, ctx)
    assert "ikke lenger gyldig" in rep[-1]


async def test_all_commands_respond():
    bot, eng, _ = await _bot_with_day()
    for name in ["today", "morning", "singles", "coupons", "odds20", "odds50", "odds100", "active", "status",
                 "updates", "results", "stats", "settings", "notifications", "help"]:
        upd, ctx, rep = fake_update(1)
        await bot._guard("reader", getattr(bot, f"cmd_{name}"))(upd, ctx)
        assert rep, name
    upd, ctx, rep = fake_update(1)
    await bot._guard("admin", bot.cmd_refresh)(upd, ctx)
    assert any("ekstra" in r for r in rep)


async def test_settings_callbacks_persist():
    bot, eng, _ = await _bot_with_day()
    for data in ["set:brief:07:30", "set:quiet:23:00-07:00", "set:notify:detaljert", "set:cat:G", "set:lg:39"]:
        upd, ctx, rep = fake_update(5, data=data)
        await bot._guard("reader", bot.on_callback)(upd, ctx)
    u = bot.user(5)
    assert u["brief_time"] == "07:30" and u["quiet_start"] == "23:00" and u["notify_level"] == "detaljert"
    assert "G" not in json.loads(u["categories_json"]) and json.loads(u["leagues_json"]) == [39]


async def test_budget_and_daily_exposure_limit():
    bot, eng, _ = await _bot_with_day()
    cid = repo.coupons_for_date(eng.db, date(2026, 10, 20))[0]["id"]
    upd, ctx, rep = fake_update(5, args=[cid, "50"])
    await bot._guard("reader", bot.cmd_placed)(upd, ctx)
    assert "budsjett" in rep[0]
    upd, ctx, rep = fake_update(5, args=["1000", "100"])
    await bot._guard("reader", bot.cmd_budget)(upd, ctx)
    upd, ctx, rep = fake_update(5, args=[cid, "80"])
    await bot._guard("reader", bot.cmd_placed)(upd, ctx)
    assert "Registrert" in rep[0]
    upd, ctx, rep = fake_update(5, args=[cid, "30"])
    await bot._guard("reader", bot.cmd_placed)(upd, ctx)
    assert "Avvist" in rep[0]
    # Personlige spill er private
    assert eng.db.one("SELECT COUNT(*) n FROM user_bets WHERE chat_id=1")["n"] == 0


async def test_ntodds_creates_new_version_and_keeps_history():
    bot, eng, _ = await _bot_with_day()
    c = repo.coupons_for_date(eng.db, date(2026, 10, 20))[0]
    legs = repo.coupon_legs(eng.db, c["id"], c["version"])
    for l in legs:
        upd, ctx, rep = fake_update(1, args=[l["id"], f"{l['odds']:.2f}".replace(".", ",")])
        await bot._guard("admin", bot.cmd_ntodds)(upd, ctx)
    versions = eng.db.all("SELECT * FROM coupons WHERE id=? ORDER BY version", (c["id"],))
    assert len(versions) == 1 + len(legs)
    assert all(v["superseded"] for v in versions[:-1]) and not versions[-1]["superseded"]
    assert versions[-1]["total_verified"] == 1 and versions[-1]["status"] == "KONTROLLERT"


def test_split_message_keeps_paragraphs():
    text = "\n\n".join(f"<b>Avsnitt {i}</b>\n" + "x" * 300 for i in range(40))
    parts = split_message(text, 1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(p.replace("\n", "") for p in parts) == text.replace("\n", "")
    for p in parts:
        assert p.count("<b>") == p.count("</b>")


def test_parse_bet_mapping():
    assert parse_bet("Match Winner", "Home") == Selection("1X2", "H")
    assert parse_bet("Asian Handicap", "Away +0.25") == Selection("AH", "A", 0.25)
    assert parse_bet("Asian Handicap", "Home -1") == Selection("AH", "H", -1.0)
    assert parse_bet("Goals Over/Under", "Under 2.5") == Selection("OU", "U", 2.5)
    assert parse_bet("Both Teams Score", "No") == Selection("BTTS", "N")
    assert parse_bet("Double Chance", "Draw/Away") == Selection("DC", "X2")
    assert parse_bet("Home/Away", "Home") == Selection("DNB", "H")
    assert parse_bet("Exact Score", "1:0") is None


async def test_apifootball_parsing_with_mocked_http():
    def handler(req: httpx.Request):
        p = req.url.path
        assert req.headers["x-apisports-key"] == "k"
        if p == "/odds":
            return httpx.Response(200, json={"errors": [], "response": [{"update": "2026-10-20T05:00:00+00:00",
                "bookmakers": [{"name": "Pinnacle", "bets": [{"name": "Match Winner", "values": [
                    {"value": "Home", "odd": "1.90"}, {"value": "Draw", "odd": "3.50"}, {"value": "Away", "odd": "4.20"}]},
                    {"name": "Goals Over/Under", "values": [{"value": "Over 2.5", "odd": "1.95"}]}]}]}]})
        if p == "/fixtures" and "ids" in req.url.params:
            return httpx.Response(200, json={"errors": [], "response": [{
                "fixture": {"id": 11, "status": {"short": "2H", "elapsed": 70}},
                "goals": {"home": 2, "away": 1}, "score": {"halftime": {"home": 1, "away": 0}, "fulltime": {"home": None, "away": None}},
                "events": [{"time": {"elapsed": 12}, "team": {"name": "A"}, "player": {"name": "P"}, "type": "Goal", "detail": "Normal Goal"},
                           {"time": {"elapsed": 50}, "team": {"name": "B"}, "player": {"name": "Q"}, "type": "Var", "detail": "Goal cancelled"}],
                "statistics": [{"team": {"name": "A"}, "statistics": [{"type": "Yellow Cards", "value": 2}, {"type": "Red Cards", "value": None}, {"type": "Corner Kicks", "value": 5}]},
                               {"team": {"name": "B"}, "statistics": [{"type": "Yellow Cards", "value": 1}, {"type": "Corner Kicks", "value": 3}]}]}]})
        if p == "/fixtures":
            return httpx.Response(200, json={"errors": [], "response": [{
                "fixture": {"id": 11, "referee": "R", "timestamp": 1792500000, "venue": {"name": "V"}, "status": {"short": "NS"}},
                "league": {"id": 103, "name": "Eliteserien", "season": 2026}, "teams": {"home": {"name": "A"}, "away": {"name": "B"}}}]})
        if p == "/injuries":
            return httpx.Response(200, json={"errors": {}, "response": [
                {"player": {"name": "X", "type": "Missing Fixture", "reason": "Knee"}, "team": {"name": "A"}}]})
        return httpx.Response(200, json={"errors": {"token": "bad"}, "response": []})

    db = DB(":memory:")
    api = APIFootball("k", db, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    fx = (await api.fixtures_on(date(2026, 10, 20)))[0]
    assert fx.league_id == 103 and fx.home == "A" and fx.kickoff.tzinfo is not None
    q = await api.odds(fx)
    assert {x.selection for x in q} == {Selection("1X2", "H"), Selection("1X2", "D"), Selection("1X2", "A"),
                                       Selection("OU", "O", 2.5)}
    assert not any(x.is_nt for x in q)  # referanseodds merkes aldri som NT
    ab = await api.absences(fx)
    assert ab[0].kind == "Ute"
    live = (await api.live(["11"]))[0]
    assert live.home_goals == 2 and live.cards == 3 and live.corners == 8 and live.ht_home == 1
    assert any(e.type == "Var" for e in live.events)


def test_backtest_runs_without_leakage_on_synthetic_data():
    import random
    from datetime import timedelta
    rnd = random.Random(1)
    teams = [f"T{i}" for i in range(10)]
    strength = {t: rnd.gauss(0, 0.3) for t in teams}
    rows, d = [], date(2025, 8, 1)
    import math
    for week in range(60):
        rnd.shuffle(teams)
        for i in range(5):
            h, a = teams[2 * i], teams[2 * i + 1]
            lh, la = 1.4 * math.exp(strength[h] - strength[a] + 0.1), 1.2 * math.exp(strength[a] - strength[h])
            hg = sum(1 for _ in range(10) if rnd.random() < lh / 10)
            ag = sum(1 for _ in range(10) if rnd.random() < la / 10)
            odds = (2.4, 3.3, 3.0)
            rows.append(Row(d + timedelta(days=7 * week), h, a, hg, ag, odds, odds, odds))
    rep = backtest_run(rows)
    assert rep.n > 100
    assert rep.first >= rows[0].d + timedelta(days=120)
    txt = rep.text()
    assert "log loss" in txt and "Kalibrering" in txt and "Forbehold" in txt
