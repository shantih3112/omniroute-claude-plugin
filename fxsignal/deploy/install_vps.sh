#!/usr/bin/env bash
# Prepare a fresh Debian/Ubuntu VPS for fxsignal. Review before running; run as root.
set -euo pipefail
apt-get update
apt-get install -y python3 python3-venv git chrony sqlite3
systemctl enable --now chrony
id fxsignal >/dev/null 2>&1 || useradd --system --home /opt/fxsignal --shell /usr/sbin/nologin fxsignal
mkdir -p /opt/fxsignal /etc/fxsignal
if [ ! -d /opt/fxsignal/src ]; then
  echo "Copy or git-clone the fxsignal project into /opt/fxsignal first." >&2; exit 1
fi
cd /opt/fxsignal
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/pip install --no-deps -e .
mkdir -p var/backups
chown -R fxsignal:fxsignal /opt/fxsignal
[ -f /etc/fxsignal/fxsignal.env ] || install -m 600 -o fxsignal -g fxsignal .env.example /etc/fxsignal/fxsignal.env
cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
echo "Edit /etc/fxsignal/fxsignal.env, then:"
echo "  sudo -u fxsignal /opt/fxsignal/.venv/bin/fxsignal check   (with the env loaded)"
echo "  systemctl enable --now fxsignal fxsignal-watchdog fxsignal-backup.timer"
