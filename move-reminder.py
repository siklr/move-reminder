#!/usr/bin/env python3
import asyncio
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time


def env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


WORK = env_float("MOVE_WORK_MINUTES", 50) * 60
BREAK = env_float("MOVE_BREAK_MINUTES", 3) * 60
NAG = env_float("MOVE_NAG_MINUTES", 4) * 60
SOUND = os.environ.get("MOVE_SOUND", "").strip()
HELPER = os.environ.get(
    "MOVE_IDLE_WATCH", os.path.expanduser("~/.local/bin/idle-watch"))

TICK_SECONDS = 5
DEFAULT_ICON = "appointment-soon"
# Critical notifications show over fullscreen apps and never steal focus.
URGENCY_CRITICAL = 2
NEVER_EXPIRE = 0

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/ocean/stereo/completion-success.oga",
]


def now():
    # BOOTTIME keeps counting during suspend.
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def gvariant_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def gdbus_notifications(method, *args):
    result = subprocess.run(
        ["gdbus", "call", "--session",
         "--dest", "org.freedesktop.Notifications",
         "--object-path", "/org/freedesktop/Notifications",
         "--method", f"org.freedesktop.Notifications.{method}", *args],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        log(f"{method} failed: {result.stderr.strip()}")
    return result.stdout


def pick_icon():
    icon = os.path.expanduser(os.environ.get("MOVE_ICON", "").strip())
    if "/" not in icon:
        return icon or DEFAULT_ICON
    if os.path.isfile(icon):
        return pathlib.Path(icon).resolve().as_uri()
    log(f"icon not found: {icon}, using {DEFAULT_ICON}")
    return DEFAULT_ICON


ICON = pick_icon()


def notify(title, body, replace_id=None):
    try:
        out = gdbus_notifications(
            "Notify",
            gvariant_quote("Move reminder"),
            str(replace_id or 0),
            gvariant_quote(ICON),
            gvariant_quote(title),
            gvariant_quote(body),
            "[]",
            f"{{'urgency': <byte {URGENCY_CRITICAL}>, "
            f"'image-path': <{gvariant_quote(ICON)}>}}",
            str(NEVER_EXPIRE),
        )
        m = re.search(r"uint32 (\d+)", out)
        return int(m.group(1)) if m else None
    except Exception as e:
        log(f"notify failed: {e}")
        return None


def close_notification(nid):
    if nid:
        try:
            gdbus_notifications("CloseNotification", str(nid))
        except Exception as e:
            log(f"close failed: {e}")


def pick_sound():
    for path in ([SOUND] if SOUND else []) + SOUND_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return None


SOUND_FILE = pick_sound()
PLAYER = shutil.which("pw-play") or shutil.which("paplay")


def play_sound():
    if SOUND_FILE and PLAYER:
        subprocess.Popen([PLAYER, SOUND_FILE],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class State:
    def __init__(self):
        self.idle = False
        self.notif_id = None
        self.start_session(now())

    def start_session(self, t):
        self.session_start = t
        self.last_nag = None
        self.nag_count = 0

    def on_idle(self):
        # You've been away for BREAK: that counts as your break.
        self.idle = True
        close_notification(self.notif_id)
        self.notif_id = None
        self.start_session(now())
        log("break detected, timer reset")

    def on_active(self):
        if self.idle:
            self.idle = False
            # Time spent away doesn't count toward the next work stretch.
            self.start_session(now())
            log("back at desk, timer started")

    def nag(self, t):
        self.nag_count += 1
        self.last_nag = t
        mins = int((t - self.session_start) // 60)
        brk = max(1, round(BREAK / 60))
        title = ("Time to get up and move" if self.nag_count == 1
                 else f"Still sitting! (reminder #{self.nag_count})")
        body = (f"{mins} min at the desk. Step away for {brk} min "
                f"and this clears on its own.")
        self.notif_id = notify(title, body, self.notif_id) or self.notif_id
        play_sound()
        log(f"nag #{self.nag_count} after {mins} min")


async def watch_idle(st):
    proc = await asyncio.create_subprocess_exec(
        HELPER, str(BREAK), stdout=asyncio.subprocess.PIPE)
    async for raw in proc.stdout:
        line = raw.decode().strip()
        if line == "idle":
            st.on_idle()
        elif line == "active":
            st.on_active()
    code = await proc.wait()
    raise SystemExit(f"idle-watch exited ({code}); letting systemd restart us")


async def ticker(st):
    while True:
        await asyncio.sleep(TICK_SECONDS)
        if st.idle:
            continue
        t = now()
        if t - st.session_start >= WORK and (
            st.last_nag is None or t - st.last_nag >= NAG
        ):
            st.nag(t)


async def main():
    if not os.access(HELPER, os.X_OK):
        raise SystemExit(f"idle-watch helper not found at {HELPER}")
    log(f"move-reminder: work={WORK/60:g}m break={BREAK/60:g}m "
        f"nag={NAG/60:g}m sound={SOUND_FILE or 'none'}")
    st = State()
    loops = asyncio.gather(watch_idle(st), ticker(st))
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, loops.cancel)
    try:
        await loops
    except asyncio.CancelledError:
        log("stopping")
    finally:
        close_notification(st.notif_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
