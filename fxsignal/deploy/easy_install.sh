#!/usr/bin/env bash
# One-command installer for fxsignal on a fresh Ubuntu/Debian server.
#
#   curl -fsSL https://raw.githubusercontent.com/shantih3112/omniroute-claude-plugin/claude/fx-signal-system/fxsignal/deploy/easy_install.sh | sudo bash
#
# It asks for two secrets (Twelve Data key, Telegram bot token), finds your Telegram ID itself,
# tests the price feed and Telegram, installs the service + watchdog + backups, starts them and
# sends you a test message. Secrets are stored only in /etc/fxsignal/fxsignal.env (mode 600).
# Re-running it updates the code and keeps your settings. `sudo fxsignal-reconfigure` asks again.
set -euo pipefail

REPO="https://github.com/shantih3112/omniroute-claude-plugin.git"
BRANCH="${FXSIGNAL_BRANCH:-claude/fx-signal-system}"
APP=/opt/fxsignal
SRC=/opt/fxsignal-src
ENVF=/etc/fxsignal/fxsignal.env
RECONF="${1:-}"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mPROBLEM\033[0m  %s\n' "$*"; }
ask()  { local __v; read -r -p "$1" __v </dev/tty; printf '%s' "$__v"; }
asks() { local __v; read -r -s -p "$1" __v </dev/tty; echo >/dev/tty; printf '%s' "$__v"; }

[ "$(id -u)" -eq 0 ] || { echo "Please run with sudo (or as root)."; exit 1; }

say "1/7  Installing system packages (a minute or two)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv git chrony curl ca-certificates >/dev/null
systemctl enable --now chrony >/dev/null 2>&1 || true
ok "packages installed, clock sync (chrony) running"

say "2/7  Downloading fxsignal ($BRANCH)"
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch -q origin "$BRANCH" && git -C "$SRC" checkout -q -B "$BRANCH" "origin/$BRANCH"
else
  git clone -q --depth 1 --branch "$BRANCH" "$REPO" "$SRC"
fi
id fxsignal >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin fxsignal
mkdir -p "$APP/var/backups" /etc/fxsignal
# copy code, never touch var/ (database, heartbeat, backups)
tar -C "$SRC/fxsignal" --exclude=./var --exclude=./data --exclude=./.venv -cf - . | tar -C "$APP" -xf -
ok "code in $APP (commit $(git -C "$SRC" rev-parse --short HEAD))"

say "3/7  Installing Python packages (a few minutes the first time)"
[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.lock.txt"
"$APP/.venv/bin/pip" install -q --no-deps -e "$APP"
ok "python environment ready"

say "4/7  Your settings"
if [ ! -s "$ENVF" ] || [ "$RECONF" = "--reconfigure" ]; then
  echo "  Paste each value and press Enter. Nothing is shown while you paste secrets; that is normal."
  TD=""
  while [ -z "$TD" ]; do TD=$(asks "  Twelve Data API key: "); done
  TOK=""
  while ! printf '%s' "$TOK" | grep -Eq '^[0-9]+:[A-Za-z0-9_-]{30,}$'; do
    TOK=$(asks "  Telegram bot token from @BotFather (looks like 123456:ABC...): ")
    printf '%s' "$TOK" | grep -Eq '^[0-9]+:[A-Za-z0-9_-]{30,}$' || echo "  That does not look like a bot token, try again."
  done
  echo "  Now open your bot in Telegram and send it any message (for example: hello)."
  ADMIN=""
  for i in $(seq 1 30); do
    J=$(curl -fsS "https://api.telegram.org/bot$TOK/getUpdates" || true)
    ADMIN=$(printf '%s' "$J" | python3 -c 'import json,sys
try:
    r=[u["message"] for u in json.load(sys.stdin).get("result",[]) if "message" in u and u["message"]["chat"]["type"]=="private"]
    print(r[-1]["from"]["id"] if r else "")
except Exception: print("")')
    NAME=$(printf '%s' "$J" | python3 -c 'import json,sys
try:
    r=[u["message"] for u in json.load(sys.stdin).get("result",[]) if "message" in u and u["message"]["chat"]["type"]=="private"]
    f=r[-1]["from"]; print((f.get("first_name","")+" @"+f.get("username","")).strip())
except Exception: print("")')
    [ -n "$ADMIN" ] && break
    [ "$i" -eq 1 ] && echo "  Waiting for your message..."
    sleep 5
  done
  if [ -z "$ADMIN" ]; then
    echo "  Did not see a message. Your numeric Telegram ID (from @userinfobot) instead:"
    ADMIN=$(ask "  Telegram user ID: ")
  else
    CONF=$(ask "  Found Telegram user '$NAME' (id $ADMIN). Is that you? [Y/n] ")
    case "$CONF" in [nN]*) ADMIN=$(ask "  Your numeric Telegram user ID: ");; esac
  fi
  umask 077
  cat > "$ENVF" <<EOF
# fxsignal secrets - keep private (chmod 600). Edit with: sudo nano $ENVF
TWELVEDATA_API_KEY=$TD
OANDA_API_TOKEN=
OANDA_HOST=https://api-fxpractice.oanda.com
TELEGRAM_BOT_TOKEN=$TOK
TELEGRAM_ADMIN_CHAT_ID=$ADMIN
TELEGRAM_ADMIN_IDS=$ADMIN
TELEGRAM_CHANNEL_ID=
WATCHDOG_HEALTH_URL=http://127.0.0.1:8087/health
WATCHDOG_RESTART_CMD=
DEADMAN_PING_URL=
EOF
  chown fxsignal:fxsignal "$ENVF"; chmod 600 "$ENVF"
  ok "settings saved to $ENVF (only readable by the service)"
else
  ok "keeping existing settings ($ENVF). To change them: sudo fxsignal-reconfigure"
fi
chown -R fxsignal:fxsignal "$APP"

say "5/7  Testing the price feed and Telegram"
set -a; . "$ENVF"; set +a
if runuser -u fxsignal -- bash -c "set -a; . $ENVF; set +a; exec $APP/.venv/bin/fxsignal feed-selftest"; then ok "price feed works"; else fail "price feed test failed (check the Twelve Data key); continuing"; fi
MSG="fxsignal installed on $(hostname). Research mode: messages are labelled RESEARCH ONLY - do not trade them. Send /status to check, /help for commands."
if curl -fsS -o /dev/null "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
     --data-urlencode "chat_id=$TELEGRAM_ADMIN_CHAT_ID" --data-urlencode "text=$MSG"; then
  ok "test message sent to your Telegram"
else
  fail "could not send a Telegram message (did you press Start in the bot chat?)"
fi

say "6/7  Installing and starting the service, watchdog and backups"
cp "$APP"/deploy/systemd/*.service "$APP"/deploy/systemd/*.timer /etc/systemd/system/
cat > /usr/local/bin/fxsignal-reconfigure <<EOF
#!/bin/sh
exec bash $APP/deploy/easy_install.sh --reconfigure
EOF
cat > /usr/local/bin/fxsignal-update <<EOF
#!/bin/sh
curl -fsSL https://raw.githubusercontent.com/shantih3112/omniroute-claude-plugin/$BRANCH/fxsignal/deploy/easy_install.sh | bash
EOF
chmod +x /usr/local/bin/fxsignal-reconfigure /usr/local/bin/fxsignal-update
systemctl daemon-reload
systemctl enable -q fxsignal fxsignal-watchdog fxsignal-backup.timer
systemctl restart fxsignal fxsignal-watchdog
systemctl start fxsignal-backup.timer
ok "services enabled (they also start automatically after a reboot)"

say "7/7  Checking it is running (loading price history takes ~2-3 minutes)"
for i in $(seq 1 60); do
  if [ -s "$APP/var/heartbeat.json" ]; then break; fi
  if ! systemctl is-active -q fxsignal; then break; fi
  sleep 5
done
if systemctl is-active -q fxsignal && [ -s "$APP/var/heartbeat.json" ]; then
  ok "fxsignal is running and writing heartbeats"
  python3 - "$APP/var/heartbeat.json" <<'PY'
import json, sys
h = json.load(open(sys.argv[1]))
print("     mode:", h.get("mode"), "| symbols:", ", ".join(f"{k}={v['status']}" for k, v in h["symbols"].items()))
PY
else
  fail "fxsignal is not healthy yet. Last log lines:"
  journalctl -u fxsignal -n 20 --no-pager || true
fi
systemctl is-active -q fxsignal-watchdog && ok "watchdog running" || fail "watchdog not running"

cat <<EOF

Done. What happens now:
  - In Telegram, send /status to your bot. It should answer within a few seconds.
  - A daily report arrives around 22:30 Oslo time, also on days without signals.
  - Everything is RESEARCH ONLY. No strategy has passed testing. Do not trade the messages.
Useful commands on this server:
  sudo systemctl status fxsignal      is it running?
  sudo journalctl -u fxsignal -f      live log (Ctrl+C to leave)
  sudo fxsignal-update                install the newest version, keep settings
  sudo fxsignal-reconfigure           change keys / Telegram ID
EOF
