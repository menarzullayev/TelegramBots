#!/usr/bin/env bash
# Runs TezMafia from the shared D: drive when the PC boots into Linux (systemd user service).
# The code, .env and data/ are the same files Windows uses, so games and wallets carry over.
# Usage, from the mounted repo:  bash tezmafia/scripts/linux/install-autostart.sh
set -euo pipefail

app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
venv="$HOME/.local/share/tezmafia/venv"   # venv on ext4: NTFS mounts handle venv symlinks badly
unit_dir="$HOME/.config/systemd/user"

echo "app: $app_dir"
mount_point="$(df --output=target "$app_dir" | tail -1)"
fs_type="$(df --output=fstype "$app_dir" | tail -1)"
echo "mount: $mount_point ($fs_type)"

if ! touch "$app_dir/data/.write-test" 2>/dev/null; then
  echo "ERROR: $app_dir/data is read-only. Turn off Windows Fast Startup, then reboot into Linux." >&2
  exit 1
fi
rm -f "$app_dir/data/.write-test"

if ! grep -qs " $mount_point " /etc/fstab; then
  echo "WARNING: $mount_point is not in /etc/fstab, so it may not be mounted at boot."
  echo "         Add it (UUID from 'lsblk -f'), e.g.:"
  echo "         UUID=<uuid> $mount_point ntfs3 uid=$(id -u),gid=$(id -g),windows_names 0 0"
fi

python3 -m venv "$venv"
"$venv/bin/pip" install -q --upgrade pip
"$venv/bin/pip" install -q -e "$app_dir"

mkdir -p "$unit_dir"
cat > "$unit_dir/tezmafia.service" <<UNIT
[Unit]
Description=TezMafia Telegram bot (shared D: drive)
After=network-online.target
Wants=network-online.target
RequiresMountsFor=$app_dir

[Service]
WorkingDirectory=$app_dir
Environment=PYTHONUTF8=1
ExecStart=$venv/bin/python -m tezmafia
Restart=always
RestartSec=10
# 75 = another instance already polls with this data directory.
RestartPreventExitStatus=75

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now tezmafia.service
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER"
systemctl --user --no-pager status tezmafia.service | head -5
