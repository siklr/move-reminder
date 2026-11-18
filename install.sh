#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

XML=/usr/share/wayland-protocols/staging/ext-idle-notify/ext-idle-notify-v1.xml
[[ -f $XML ]] || { echo "Missing $XML (install wayland-protocols)"; exit 1; }

build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
wayland-scanner client-header "$XML" "$build/ext-idle-notify-v1-client-protocol.h"
wayland-scanner private-code  "$XML" "$build/ext-idle-notify-v1-protocol.c"
cc -O2 -Wall -I"$build" -o "$build/idle-watch" \
   idle-watch.c "$build/ext-idle-notify-v1-protocol.c" -lwayland-client

install -Dm755 "$build/idle-watch"   ~/.local/bin/idle-watch
install -Dm755 move-reminder.py      ~/.local/bin/move-reminder.py
install -Dm644 move-reminder.service ~/.config/systemd/user/move-reminder.service

systemctl --user daemon-reload
systemctl --user enable move-reminder
systemctl --user restart move-reminder
echo "Installed. Logs: journalctl --user -u move-reminder -f"
