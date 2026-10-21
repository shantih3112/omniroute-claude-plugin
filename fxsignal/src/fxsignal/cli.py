"""Command-line entry point: `fxsignal <command>` (or `python -m fxsignal.cli`).

  serve      run the live paper service (needs OANDA_API_TOKEN; Telegram optional)
  replay     run the real service on historical M1 data with a simulated clock (no network)
  size       private position-size calculator
  plan       illustrative capital-planning Monte Carlo (assumed returns)
  backup     consistent SQLite backup
  check      configuration/credential presence check (never prints secret values)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _cmd_serve(a):
    from .live.app import serve
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    asyncio.run(serve(a.config, Path(a.base_dir).resolve()))


def _cmd_replay(a):
    from .data import loaders as L
    from .data.resample import resample
    from .live.app import load_config, replay
    from .signals.store import Store
    from .telegram.client import Outbox, TelegramClient

    cfg = load_config(a.config)
    cfg["symbols"] = a.symbols.split(",") if a.symbols else cfg["symbols"]
    if a.strategies:
        cfg["strategies"] = [{"family": f, "params": {}, "status": "research"} for f in a.strategies.split(",")]
    cfg.setdefault("news", {})["fail_closed"] = False  # no historical calendar exists for replays
    base = Path(a.base_dir).resolve()
    store = Store(base / a.db)
    start = pd.Timestamp(a.start, tz="UTC")
    m1 = {s: (L.load_dukascopy_m1(s) if a.source == "dukascopy" else L.load_oanda_m1(s)) for s in cfg["symbols"]}
    hist = {s: resample(df[df.index < start], "H1") for s, df in m1.items()}
    ob = None
    if a.capture:
        cap = Path(a.capture)

        class _Cap:  # writes "sent" messages to a file instead of Telegram
            def __init__(self):
                self.n = 0

            async def send(self, chat, text, silent=False):
                from .telegram.client import SendResult
                self.n += 1
                with cap.open("a") as f:
                    f.write(f"--- to {chat} ---\n{text}\n\n")
                return SendResult(True, self.n)

        ob = Outbox(store, _Cap(), {"admin": "admin-chat", "broadcast": "channel"}, max_per_minute=10**6)
    svc = asyncio.run(replay(cfg, store, m1, start, int(a.days * 1440), base, hist, ob))
    print(json.dumps(svc.health(), indent=1, default=str))
    print(json.dumps({"events": {r[0]: r[1] for r in store.conn.execute("SELECT kind, COUNT(*) FROM events GROUP BY kind")},
                      "outbox": store.outbox_stats()}, indent=1))


def _cmd_size(a):
    from . import instruments
    from .risk.sizing import size_position
    prices = json.loads(a.prices) if a.prices else {}
    prices.setdefault(a.symbol.upper(), a.entry)
    inst = instruments.get(a.symbol)
    r = size_position(inst, a.equity, a.ccy.upper(), a.risk, a.entry, a.stop, prices,
                      spread_price=inst.spread_pips * inst.pip_size)
    print(json.dumps(r.__dict__, indent=1))


def _cmd_plan(a):
    from .research.planner import PlanInputs, simulate
    p = PlanInputs(start_capital=a.start, monthly_contribution=a.monthly, monthly_costs=a.costs, years=a.years,
                   trades_per_month=a.trades, risk_pct=a.risk, expectancy_r=a.exp_r, r_sd=a.r_sd)
    r = simulate(p)
    r.pop("paths_quantiles")
    print(json.dumps(r, indent=1))


def _cmd_backup(a):
    from .signals.store import Store
    st = Store(a.db)
    dest = Path(a.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    st.backup(dest)
    print(f"backup written: {dest}")


def _cmd_check(a):
    feed_ok = bool(os.environ.get("OANDA_API_TOKEN") or os.environ.get("TWELVEDATA_API_KEY"))
    print(f"{'price feed':24s} {'set' if feed_ok else 'MISSING':8s} OANDA_API_TOKEN (1-minute) or TWELVEDATA_API_KEY (hourly)")
    need = {"TELEGRAM_BOT_TOKEN": "Telegram delivery",
            "TELEGRAM_ADMIN_CHAT_ID": "admin chat", "TELEGRAM_ADMIN_IDS": "admin authorisation",
            "TELEGRAM_CHANNEL_ID": "broadcast channel (only used for validated strategies)"}
    ok = feed_ok
    for k, why in need.items():
        present = bool(os.environ.get(k))
        ok &= present or k == "TELEGRAM_CHANNEL_ID"
        print(f"{k:24s} {'set' if present else 'MISSING':8s} {why}")
    from .risk.ftmo import FtmoProfile
    for f in sorted((ROOT / "config" / "ftmo").glob("*.yaml")):
        p = FtmoProfile.load(f)
        print(f"FTMO profile {f.name}: {p.challenge_use_allowed()[1]}")
    sys.exit(0 if ok else 1)


def _cmd_run_once(a):
    """One scheduled cycle; used by the GitHub Actions workflow (no server needed)."""
    import httpx
    from .live.app import load_config, run_once, telegram_from_env
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # request URLs can contain API keys (Twelve Data uses ?apikey=); never log them
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    cfg = load_config(a.config)
    tg, chats, admins = telegram_from_env()
    extra = os.environ.get("TELEGRAM_ADMIN_ID", "").strip()
    if extra.isdigit():
        admins.add(int(extra))
        chats["admin"] = chats.get("admin") or extra

    async def go():
        async with httpx.AsyncClient(timeout=20) as http:
            try:
                return await run_once(cfg, Path(a.base_dir).resolve(), tg=tg, chats=chats, admins=admins, http=http)
            finally:
                if tg:
                    await tg.close()
    info = asyncio.run(go())
    # this log is public for public repositories: counts and statuses only
    print(json.dumps({k: info.get(k) for k in ("new_bars", "cycle", "sent", "outbox", "symbols")}, default=str))


def _cmd_feed_selftest(a):
    """Fetch a few real bars from the configured feed and check them. Uses ~2 API credits."""
    from .live.app import load_config, make_feed

    async def go():
        try:
            feed = make_feed(load_config(a.config))
        except Exception as ex:
            print(f"FAIL: {ex}")
            return 1
        try:
            h = await feed.history_h1(a.symbol, 30)
            print(f"feed={feed.name} symbol={a.symbol} bars={len(h)}")
            if len(h) == 0:
                print("FAIL: no completed bars returned")
                return 1
            print(h.tail(3).to_string())
            age = (pd.Timestamp.now(tz="UTC") - (h.index[-1] + pd.Timedelta(hours=1))).total_seconds() / 3600
            sane = bool(((h.high >= h[["open", "close"]].max(axis=1)) & (h.low <= h[["open", "close"]].min(axis=1))).all())
            print(f"newest completed bar closed {age:.1f} h ago; OHLC consistent: {sane}")
            print("OK" if sane and (age < 2 or age > 40) else "CHECK: data older than expected (market closed?)")
            return 0
        except Exception as ex:
            print(f"FAIL: could not get prices from {feed.name}: {type(ex).__name__}: {str(ex)[:200]}")
            return 1
        finally:
            await feed.close()
    sys.exit(asyncio.run(go()))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fxsignal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    s.add_argument("--base-dir", default=str(ROOT))
    s.set_defaults(fn=_cmd_serve)
    r = sub.add_parser("replay")
    r.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    r.add_argument("--base-dir", default=str(ROOT))
    r.add_argument("--db", default="var/replay.sqlite")
    r.add_argument("--start", required=True)
    r.add_argument("--days", type=float, default=5)
    r.add_argument("--symbols", default="EURUSD,GBPUSD,AUDUSD,USDCAD")
    r.add_argument("--strategies", default="")
    r.add_argument("--source", choices=["dukascopy", "oanda"], default="dukascopy")
    r.add_argument("--capture", default="", help="write would-be Telegram messages to this file")
    r.set_defaults(fn=_cmd_replay)
    z = sub.add_parser("size")
    for k, t in (("symbol", str), ("equity", float), ("ccy", str), ("risk", float), ("entry", float), ("stop", float)):
        z.add_argument(k, type=t)
    z.add_argument("--prices", default="", help='JSON of conversion prices, e.g. {"EURUSD":1.08}')
    z.set_defaults(fn=_cmd_size)
    p = sub.add_parser("plan")
    p.add_argument("--start", type=float, default=1000)
    p.add_argument("--monthly", type=float, default=0)
    p.add_argument("--costs", type=float, default=15)
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--trades", type=float, default=20)
    p.add_argument("--risk", type=float, default=0.5)
    p.add_argument("--exp-r", type=float, default=0.0, help="ASSUMED expectancy in R per trade")
    p.add_argument("--r-sd", type=float, default=1.2)
    p.set_defaults(fn=_cmd_plan)
    b = sub.add_parser("backup")
    b.add_argument("--db", default=str(ROOT / "var" / "fxsignal.sqlite"))
    b.add_argument("--dest", required=True)
    b.set_defaults(fn=_cmd_backup)
    o = sub.add_parser("run-once")
    o.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    o.add_argument("--base-dir", default=str(ROOT))
    o.set_defaults(fn=_cmd_run_once)
    f = sub.add_parser("feed-selftest")
    f.add_argument("--config", default=str(ROOT / "config" / "default.yaml"))
    f.add_argument("--symbol", default="EURUSD")
    f.set_defaults(fn=_cmd_feed_selftest)
    c = sub.add_parser("check")
    c.set_defaults(fn=_cmd_check)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
