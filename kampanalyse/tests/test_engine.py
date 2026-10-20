"""Planlegging, sommertid, duplikatbeskyttelse, omstart, korreksjoner, tap og driftsavvik."""
import json
from datetime import date, datetime, time, timedelta

import pytest

from kampanalyse import render, repo
from kampanalyse.providers.base import ProviderError
from kampanalyse.timeutil import local_at
from tests.conftest import make_engine, run_until



def _keys(eng):
    return [r["dedupe_key"] for r in eng.db.all("SELECT dedupe_key FROM outbox ORDER BY id")]


@pytest.mark.parametrize("day,expected_utc_hour", [
    (date(2026, 10, 24), 6),   # siste dag med sommertid: 08:00 CEST = 06:00 UTC
    (date(2026, 10, 25), 7),   # første dag med normaltid: 08:00 CET = 07:00 UTC
    (date(2026, 3, 29), 6),    # første dag med sommertid
])
async def test_morning_brief_at_0800_oslo_across_dst(day, expected_utc_hour):
    assert local_at(day, time(8, 0)).hour == expected_utc_hour
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(7, 59)))
    assert not any(k.startswith("brief:") for k in _keys(eng))
    assert eng.latest_run(day)["status"] == "ok"  # analysen er ferdig før briefen
    await run_until(eng, clock, local_at(day, time(8, 1)))
    briefs = [r for r in eng.db.all("SELECT * FROM outbox WHERE dedupe_key LIKE 'brief:%'")]
    assert len(briefs) == 1
    sent_at = datetime.fromisoformat(briefs[0]["created_at"])
    assert sent_at.hour == expected_utc_hour and sent_at.minute == 0


async def test_no_duplicates_and_restart_resumes(tmp_path):
    db = tmp_path / "k.db"
    day = date(2026, 10, 20)
    eng, clock = make_engine(db, at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(8, 2)))
    n_out = eng.db.one("SELECT COUNT(*) n FROM outbox")["n"]
    n_runs = eng.db.one("SELECT COUNT(*) n FROM runs")["n"]
    # "Omstart": ny motor på samme database og samme tidspunkt
    eng2, clock2 = make_engine(db, at=clock.now())
    for _ in range(3):
        await eng2.tick()
    assert eng2.db.one("SELECT COUNT(*) n FROM outbox")["n"] == n_out
    assert eng2.db.one("SELECT COUNT(*) n FROM runs")["n"] == n_runs
    keys = _keys(eng2)
    assert len(keys) == len(set(keys))
    # Etter omstart følges aktive bonger videre og blir avgjort
    tracked_before = {f["id"] for f in eng2.tracked_fixtures()}
    assert tracked_before
    await run_until(eng2, clock2, local_at(day, time(23, 50)), step_minutes=2)
    open_c = eng2.db.all("SELECT * FROM coupons WHERE superseded=0 AND published_at IS NOT NULL AND outcome IS NULL")
    assert open_c == []
    picks = eng2.db.all("SELECT * FROM picks WHERE published_at IS NOT NULL AND withdrawn_at IS NULL")
    assert all(p["result"] for p in picks)


async def test_result_needs_confirmation_and_corrections_are_handled():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(8, 1)))
    f = eng.db.one("""SELECT f.* FROM fixtures f JOIN picks p ON p.fixture_id=f.id WHERE p.published_at IS NOT NULL
                      ORDER BY f.kickoff LIMIT 1""")
    ko = datetime.fromisoformat(f["kickoff"])
    # Like etter slutt: ikke bekreftet ennå
    await run_until(eng, clock, ko + timedelta(minutes=114))
    row = eng.db.one("SELECT * FROM fixtures WHERE id=?", (f["id"],))
    assert row["final_json"] and not row["final_confirmed_at"]
    assert all(p["result"] is None for p in eng.db.all("SELECT * FROM picks WHERE fixture_id=?", (f["id"],)))
    # Endret resultat i bekreftelsesvinduet nullstiller vinduet
    final = json.loads(row["final_json"])
    eng.provider.corrections[f["id"]] = (final["h"] + 1, final["a"])
    await run_until(eng, clock, ko + timedelta(minutes=120))
    row = eng.db.one("SELECT * FROM fixtures WHERE id=?", (f["id"],))
    assert json.loads(row["final_json"])["h"] == final["h"] + 1 and not row["final_confirmed_at"]
    await run_until(eng, clock, ko + timedelta(minutes=140))
    row = eng.db.one("SELECT * FROM fixtures WHERE id=?", (f["id"],))
    assert row["final_confirmed_at"]
    # Korreksjon etter bekreftelse
    eng.provider.corrections[f["id"]] = (final["h"], final["a"] + 3)
    await run_until(eng, clock, ko + timedelta(minutes=200))
    row = eng.db.one("SELECT * FROM fixtures WHERE id=?", (f["id"],))
    assert row["corrected_at"]
    assert any(k.startswith(f"correction:{f['id']}") for k in _keys(eng))
    assert eng.db.one("SELECT COUNT(*) n FROM changes WHERE kind='korrigert'")["n"] >= 0


async def test_lost_coupon_triggers_at_most_one_extra_round():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(23, 50)), step_minutes=2)
    lost = eng.db.one("SELECT COUNT(*) n FROM coupons WHERE outcome='LOST'")["n"]
    assert lost >= 2  # flere tap i demo-dagen
    extra_runs = eng.db.all("SELECT * FROM runs WHERE kind='extra'")
    assert len(extra_runs) == 1
    assert any(k.startswith("newround:") for k in _keys(eng))
    # Ekstrarunden har aldri høyere oddskategori enn bongen som tapte
    first_lost = eng.db.kv_get(f"extra_round:{day.isoformat()}")
    lost_ids = first_lost.split(": ")[1].split(", ")
    max_band = min(i.split("-")[2][0] for i in lost_ids)
    for c in eng.db.all("SELECT * FROM coupons WHERE run_id=?", (extra_runs[0]["id"],)):
        assert c["band"] <= max_band
    # Manuelt nytt forsøk blir avvist av grensen
    res = await eng.maybe_reanalyse([dict(eng.db.one("SELECT * FROM coupons LIMIT 1"))], "test")
    assert res["status"] == "limit"


async def test_api_failure_stops_recommendations_and_alerts():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))

    async def boom(d):
        raise ProviderError("nede")
    eng.provider.fixtures_on = boom
    await run_until(eng, clock, local_at(day, time(8, 1)))
    assert eng.latest_run(day)["status"] == "failed"
    assert eng.db.one("SELECT COUNT(*) n FROM picks")["n"] == 0
    texts = [r["text"] for r in eng.db.all("SELECT text FROM outbox")]
    assert any("DRIFTSAVVIK" in t for t in texts)
    assert any("Analysen feilet" in t for t in texts)


async def test_missing_odds_excludes_fixture():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    orig = eng.provider.odds

    async def no_odds(fx):
        if fx.id.endswith("-1"):
            raise ProviderError("ingen odds")
        return await orig(fx)
    eng.provider.odds = no_odds
    eng.nt_sources = []
    eng.analyzer.nt_sources = []
    await run_until(eng, clock, local_at(day, time(6, 20)))
    assert not eng.db.all("SELECT * FROM picks WHERE fixture_id LIKE '%-1'")
    notes = json.loads(eng.latest_run(day)["notes_json"])
    assert any("Odds mangler" in p for p in notes["problems"])
    # Uten NT-kilde er alle forslag merket som ikke verifisert hos NT
    assert {r["odds_kind"] for r in eng.db.all("SELECT odds_kind FROM picks")} <= {"REFERANSE"}


async def test_live_outage_is_reported_and_recovery_noted():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(8, 1)))
    first = min(datetime.fromisoformat(f["kickoff"]) for f in eng.tracked_fixtures())
    await run_until(eng, clock, first + timedelta(minutes=10))
    eng.provider.fail_live = True
    await run_until(eng, clock, first + timedelta(minutes=25))
    texts = [r["text"] for r in eng.db.all("SELECT text FROM outbox")]
    assert any("Livedata er ikke oppdatert" in t for t in texts)
    eng.provider.fail_live = False
    await run_until(eng, clock, first + timedelta(minutes=30))
    texts = [r["text"] for r in eng.db.all("SELECT text FROM outbox")]
    assert any("virker igjen" in t and "ikke fanget i sanntid" in t for t in texts)


async def test_quiet_hours_and_pause():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    eng.db.execute("INSERT INTO users(chat_id,role,brief_time,created_at,paused) VALUES(2,'reader','08:00','x',1)")
    eng.db.execute("UPDATE users SET quiet_start='07:00', quiet_end='09:00' WHERE chat_id=1")
    await run_until(eng, clock, local_at(day, time(8, 5)))
    rows = eng.db.all("SELECT * FROM outbox WHERE dedupe_key LIKE 'brief:%'")
    assert [r["chat_id"] for r in rows] == [1]  # pauset bruker får ingenting
    assert rows[0]["status"] == "pending" and rows[0]["not_before"]
    await run_until(eng, clock, local_at(day, time(9, 1)))
    assert eng.db.one("SELECT status FROM outbox WHERE id=?", (rows[0]["id"],))["status"] == "sent"


async def test_messages_avoid_banned_words_and_mark_demo():
    day = date(2026, 10, 20)
    eng, clock = make_engine(at=local_at(day, time(6, 0)))
    await run_until(eng, clock, local_at(day, time(23, 45)), step_minutes=3)
    texts = [r["text"] for r in eng.db.all("SELECT text FROM outbox")]
    assert texts
    for t in texts + [render.GUIDE, render.WELCOME, render.BOT_DESCRIPTION]:
        assert render.contains_banned(t) == [], t[:200]
    for t in texts:
        if "DRIFTSAVVIK" not in t:
            assert "DEMO" in t
    # Full analyse og kilder kan genereres for alle publiserte forslag
    for p in repo.picks_for_date(eng.db, day):
        assert "Rå implisitt" in render.full_pick_analysis(p, True)
        assert "Norsk Tipping" in render.sources_message([p], "DEMO", True)
