# Operations: setup, deployment, monitoring, recovery

## 1. What you need to provide
| Item | How | Notes |
|---|---|---|
| Price feed — **either** | | |
| … Twelve Data API key (start here) | Sign up free at twelvedata.com → dashboard → API key → `TWELVEDATA_API_KEY` | Free plan: 8 calls/min, 800/day → **hourly** bars for 11 pairs (~264 calls/day). One price series, no ask (spreads modelled). Paper entries use a live quote at publication; stops/targets are checked on hourly bars (stop-first, conservative). |
| … OANDA practice API token (later) | Free practice account at oanda.com → Manage API Access → `OANDA_API_TOKEN` | **1-minute** bars with bid and ask. If set, it is used automatically instead of Twelve Data. |
| Telegram bot | Talk to @BotFather → `/newbot` → token | Keep the token secret; it is only read from the env file |
| Your Telegram user ID | e.g. send `/start` to @userinfobot | Goes in `TELEGRAM_ADMIN_IDS` |
| Admin chat ID | Send any message to your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `chat.id` | Private chat = your user ID |
| Broadcast channel (later) | Create a **private** channel, add the bot as admin with "post messages" only | Not used until a strategy passes the gates |
| Discussion group (optional, later) | Link a group to the channel; do **not** make the bot an admin there | Commands from non-admins are ignored |
| VPS | Any Debian/Ubuntu host, 1–2 vCPU, 2 GB RAM, ~5–10 USD/month | Choose a region near London for lower feed latency |
| Dead-man switch | e.g. a free healthchecks.io check, ping URL in `DEADMAN_PING_URL` | Alerts you if the whole VPS dies |

## 2. Install on a VPS (systemd)
```bash
# as root on the VPS
git clone <your repo> /opt/fxsignal-src && cp -r /opt/fxsignal-src/fxsignal /opt/fxsignal
/opt/fxsignal/deploy/install_vps.sh
nano /etc/fxsignal/fxsignal.env        # fill in tokens (file is chmod 600)
set -a; . /etc/fxsignal/fxsignal.env; set +a
sudo -E -u fxsignal /opt/fxsignal/.venv/bin/fxsignal check
sudo -E -u fxsignal /opt/fxsignal/.venv/bin/fxsignal feed-selftest     # fetches ~30 real hourly bars (2 credits)
systemctl enable --now fxsignal fxsignal-watchdog fxsignal-backup.timer
journalctl -u fxsignal -f
```
Docker alternative: `docker compose up -d --build` (state in the `fxdata` volume).

## 3. Verify it is actually running (do not assume)
1. `systemctl status fxsignal fxsignal-watchdog` – both active.
2. `curl -s 127.0.0.1:8087/health | python3 -m json.tool` – symbols `ok` (or `market_closed` at weekends).
3. Send `/status` to the bot from your account – reply arrives.
4. Next day: the daily report arrives at ~22:30 Oslo time, including on days with no signals.
5. Kill test: `systemctl kill -s KILL fxsignal` → systemd restarts it within ~10 s; `/status` still lists the same active signals; no duplicate messages.
6. Watchdog test: `systemctl stop fxsignal` → within ~2–3 min the watchdog alerts the admin chat; start it again → "recovered".
7. Dead-man test: stop the watchdog → healthchecks.io alerts after its grace period.

## 4. Monitoring
| Signal | Where | Threshold |
|---|---|---|
| Heartbeat age | watchdog | > 120 s → alert; optional restart after 300 s |
| Per-symbol data status | `/status`, `/health`, daily report | `stale` > 180 s during market hours blocks signals |
| Calendar freshness | `/news`, daily report | > 26 h old → new signals blocked (fail-closed) |
| Outbox | `/status` | `failed` > 0 → incident logged; check token/chat IDs |
| Clock drift | watchdog (hourly) | > 5 s → alert; check `chronyc tracking` |
| Disk/memory | `systemd` `MemoryMax=1G`; `df -h` | backups pruned after 14 days |

## 5. Failure behaviour (what pauses, what continues)
| Failure | New signals | Tracking of existing signals | Delivery | Alert |
|---|---|---|---|---|
| Price feed down for one symbol | paused for that symbol | paused for that symbol (no prices) | continues | incident + `/status`, daily report |
| Price feed down entirely | paused | paused; resumes from the bars fetched on reconnect | continues | watchdog "data degraded" |
| Calendar unavailable/stale | **paused (fail-closed)** | continues | continues | daily report, `/news` |
| Telegram API down | continue to be generated and stored | continues | queued in outbox, retried with backoff (8 tries), then `failed` + incident | watchdog (if the token works for it) / journal |
| Process crash | – | resumes after restart from DB state (`track:*` keys) | resumes; dedupe keys prevent repeats | systemd restarts; watchdog notes heartbeat gap |
| Database error | cycle aborts → nothing published (fail-closed) | stops | stops | heartbeat goes stale → watchdog |
| Server clock drift | bars judged "not complete"/stale → signals blocked | – | – | watchdog drift alert |
| Kill switch (`/kill on` or `var/KILL_SWITCH`) | blocked | continues | continues | – |
| Broker ambiguous order status | not applicable: no execution exists. If execution is ever added, an unknown order status must be reconciled with the broker before any retry. | | | |

## 6. Backups and restore
* Every 6 h: `fxsignal backup` (SQLite online backup API, consistent while running) to `var/backups/`, kept 14 days. Copy off-host (e.g. `rclone` to object storage) for disaster recovery.
* Restore: `systemctl stop fxsignal; cp var/backups/<file>.sqlite var/fxsignal.sqlite; chown fxsignal: var/fxsignal.sqlite; systemctl start fxsignal`. Signals issued after the backup are lost from the DB but remain in Telegram history; note the gap as an incident.

## 7. Troubleshooting
| Symptom | Check |
|---|---|
| `fxsignal check` says MISSING | env file not loaded: `set -a; . /etc/fxsignal/fxsignal.env; set +a` |
| `OANDA 401` in journal | token wrong or for the other environment (practice vs live host) |
| No messages, outbox `pending` grows | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ADMIN_CHAT_ID` wrong, or you never pressed Start in the bot chat |
| `/status` gets no reply | your user ID is not in `TELEGRAM_ADMIN_IDS` (non-admins are ignored silently by design) |
| All symbols `stale` | feed host unreachable, or clock wrong (`timedatectl`) |
| Every signal rejected with "calendar unavailable" | calendar URL blocked/changed; `/news`; consider a paid calendar API |

## 8. Changing strategies or limits
Edit `config/default.yaml`, then `systemctl restart fxsignal`. Strategy status (`research`,
`paper_forward`) must follow `docs/SCORECARD.md`; changing it without passing the gates defeats
the purpose of the system. Keep the previous config in git for rollback.
