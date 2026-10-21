"""Independent watchdog (separate process / systemd unit).

Checks the service heartbeat file and the local health endpoint. On failure it:
  * sends ONE alert per incident to the admin chat via its own minimal Telegram call
    (so it works even if the main process is hung), repeated at most every `realert_min`;
  * optionally runs a restart command (e.g. `systemctl restart fxsignal`) after `restart_after_s`;
  * pings an external dead-man's-switch URL (e.g. healthchecks.io) only while healthy, so an
    outside service alerts you if the whole VPS dies — the one failure no local process can report.

It also checks clock drift against an HTTPS server's Date header (coarse, ±2 s resolution).
"""
from __future__ import annotations

import email.utils
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


def check(hb_path: Path, max_age_s: float, health_url: str | None) -> tuple[bool, str]:
    if not hb_path.exists():
        return False, "heartbeat file missing"
    try:
        hb = json.loads(hb_path.read_text())
    except Exception as ex:
        return False, f"heartbeat unreadable: {ex!r}"
    age = time.time() - hb_path.stat().st_mtime
    if age > max_age_s:
        return False, f"heartbeat {age:.0f}s old (service hung or stopped)"
    bad = [f"{s}:{v['status']}" for s, v in hb.get("symbols", {}).items() if v["status"] not in ("ok", "market_closed")]
    if health_url:
        try:
            r = httpx.get(health_url, timeout=5)
            if r.status_code != 200:
                return False, f"health endpoint {r.status_code}; degraded: {', '.join(bad)}"
        except httpx.HTTPError as ex:
            return False, f"health endpoint unreachable: {type(ex).__name__}"
    if bad:
        return False, "data degraded: " + ", ".join(bad)
    return True, "ok"


def clock_drift_s(url: str = "https://www.google.com") -> float | None:
    try:
        t0 = time.time()
        r = httpx.head(url, timeout=5)
        t1 = time.time()
        server = email.utils.parsedate_to_datetime(r.headers["date"]).timestamp()
        return (t0 + t1) / 2 - server
    except Exception:
        return None


def alert(text: str) -> bool:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    if not tok or not chat:
        print("ALERT (no Telegram configured):", text, file=sys.stderr)
        return False
    try:
        r = httpx.post(f"{base}/bot{tok}/sendMessage", json={"chat_id": chat, "text": f"WATCHDOG: {text}"}, timeout=10)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def main() -> None:
    base = Path(os.environ.get("FXSIGNAL_HOME", Path(__file__).resolve().parents[3]))
    hb = base / os.environ.get("FXSIGNAL_HEARTBEAT", "var/heartbeat.json")
    max_age = float(os.environ.get("WATCHDOG_MAX_AGE_S", "120"))
    health = os.environ.get("WATCHDOG_HEALTH_URL", "http://127.0.0.1:8087/health")
    restart_cmd = os.environ.get("WATCHDOG_RESTART_CMD", "")
    restart_after = float(os.environ.get("WATCHDOG_RESTART_AFTER_S", "300"))
    deadman = os.environ.get("DEADMAN_PING_URL", "")
    realert = float(os.environ.get("WATCHDOG_REALERT_MIN", "30")) * 60
    interval = float(os.environ.get("WATCHDOG_INTERVAL_S", "30"))
    grace = float(os.environ.get("WATCHDOG_STARTUP_GRACE_S", "600"))  # history load after (re)start
    started = time.time()
    bad_since, last_alert, last_drift = None, 0.0, 0.0
    while True:
        ok, why = check(hb, max_age, health)
        now = time.time()
        if not ok and now - started < grace:
            time.sleep(interval)
            continue
        if now - last_drift > 3600:
            d = clock_drift_s()
            last_drift = now
            if d is not None and abs(d) > 5:
                alert(f"clock drift {d:+.1f}s vs HTTPS Date header - check chrony/NTP")
        if ok:
            if bad_since is not None:
                alert("recovered: " + why)
            bad_since = None
            if deadman:
                try:
                    httpx.get(deadman, timeout=10)
                except httpx.HTTPError:
                    pass
        else:
            if bad_since is None:
                bad_since = now
            if now - last_alert > realert:
                alert(why)
                last_alert = now
            if restart_cmd and now - bad_since > restart_after and "heartbeat" in why:
                subprocess.run(restart_cmd, shell=True, check=False)
                bad_since = now
        time.sleep(interval)


if __name__ == "__main__":
    main()
