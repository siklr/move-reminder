# move-reminder

Nags you to get up after a long stretch at the desk, then clears itself once you actually step away. There is nothing to dismiss or snooze.

- After 50 minutes of activity, it shows a critical KDE notification and plays a sound. Critical notifications appear over fullscreen apps and never steal focus.
- The nag repeats every 4 minutes until you take a break.
- Being away from the keyboard and mouse for 3 minutes clears the notification and resets the timer.

Idle detection comes from the compositor through a small helper, `idle-watch`. It only hears "no input for N seconds" and "input again", so it never sees keys or mouse movement and needs no special permissions. Nothing leaves your machine.

## Requirements

- KDE Plasma on Wayland, with KWin 6.4 or newer
- systemd user services
- `pw-play` or `paplay` for sound (optional)

On Arch:

```bash
sudo pacman -S --needed base-devel wayland wayland-protocols python glib2
```

## Install

```bash
./install.sh
```

This builds `idle-watch`, copies the files into `~/.local/bin` and `~/.config/systemd/user`, then enables and restarts the service. Run it again to update.

Watch the logs with:

```bash
journalctl --user -u move-reminder -f
```

## Settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `MOVE_WORK_MINUTES` | `50` | Activity before the first nag |
| `MOVE_BREAK_MINUTES` | `3` | Time away that counts as a break |
| `MOVE_NAG_MINUTES` | `4` | Time between repeat nags |
| `MOVE_ICON` | `appointment-soon` | Icon theme name, or a path to an image |
| `MOVE_SOUND` | First available system sound | Path to a sound file |
| `MOVE_IDLE_WATCH` | `~/.local/bin/idle-watch` | Path to the helper |

`install.sh` overwrites the installed service file, so keep your own settings in a drop-in:

```bash
systemctl --user edit move-reminder
```

```ini
[Service]
Environment=MOVE_WORK_MINUTES=45
Environment=MOVE_ICON=%h/Pictures/move.png
```

Then apply them:

```bash
systemctl --user restart move-reminder
```

## Uninstall

```bash
systemctl --user disable --now move-reminder
rm ~/.local/bin/idle-watch ~/.local/bin/move-reminder.py ~/.config/systemd/user/move-reminder.service
rm -rf ~/.config/systemd/user/move-reminder.service.d
systemctl --user daemon-reload
```

## License

[MIT](LICENSE)
