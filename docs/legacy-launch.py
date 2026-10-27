#!/usr/bin/env python3
"""Open one selected spacedesk viewer, leaving the primary Linux screen free."""
import argparse
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
MONITORS = [(8091, 0, 0, 1920, 1080), (8092, 3840, 0, 1366, 768)]


def profile_for(number):
    return HOME / ".cache" / "spacedesk" / f"chrome-monitor-{number}"


def browser_pids(number):
    profile_arg = f"--user-data-dir={profile_for(number)}"
    pids = []
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            raw = (process / "cmdline").read_bytes().decode(errors="replace")
            # Chrome may rewrite cmdline into one space-separated argv string.
            args = shlex.split(raw.replace("\0", " "))
            if (args and args[0] == "/opt/google/chrome/chrome"
                    and profile_arg in args
                    and not any(arg.startswith("--type=") for arg in args)):
                pids.append(int(process.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            pass
    return pids


def close_browser(number):
    for pid in browser_pids(number):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(50):
        if not browser_pids(number):
            return
        time.sleep(0.1)
    raise RuntimeError(f"El visor {number} todavia esta cerrandose; no se abre un duplicado.")


def place_window(number):
    # Chrome's --window-position/--start-fullscreen are not reliable for app
    # windows under GNOME. Use its existing X11 window and the actual monitor.
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkX11", "3.0")
    from gi.repository import Gdk, GdkX11

    pids = set(browser_pids(number))
    window_id = None
    for _ in range(40):
        root = subprocess.check_output(["xprop", "-root", "_NET_CLIENT_LIST"], text=True)
        for candidate in re.findall(r"0x[0-9a-fA-F]+", root):
            prop = subprocess.run(["xprop", "-id", candidate, "_NET_WM_PID"],
                                  text=True, capture_output=True)
            match = re.search(r"= (\d+)", prop.stdout)
            if match and int(match.group(1)) in pids:
                window_id = int(candidate, 16)
                break
        if window_id is not None:
            break
        time.sleep(0.1)
    if window_id is None:
        raise RuntimeError(f"No se encontro la ventana del monitor {number}.")

    _, x, y, width, height = MONITORS[number - 1]
    display = Gdk.Display.get_default()
    monitor = next((i for i in range(display.get_n_monitors())
                    if (display.get_monitor(i).get_geometry().x,
                        display.get_monitor(i).get_geometry().y) == (x, y)), None)
    if monitor is None:
        raise RuntimeError(f"No se encuentra el monitor fisico en {x},{y}.")
    window = GdkX11.X11Window.foreign_new_for_display(display, window_id)
    window.unmaximize()
    window.move_resize(x + 10, y + 40, width - 20, height - 80)
    window.fullscreen_on_monitor(monitor)
    window.focus(Gdk.CURRENT_TIME)
    display.sync()


def status(number):
    port = MONITORS[number - 1][0]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=1) as response:
        return json.load(response)


def wait_for_stream(number, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = status(number)
        if current["state"] == "streaming":
            return current
        if current["state"] == "disconnected":
            raise RuntimeError(current["message"])
        time.sleep(0.2)
    raise RuntimeError(f"El monitor {number} no recibio imagen de Windows.")


def open_monitor(number):
    subprocess.run(["systemctl", "--user", "start", f"spacedesk-monitor@{number}"], check=True)
    port, x, y, width, height = MONITORS[number - 1]
    url = f"http://127.0.0.1:{port}/"
    for attempt in range(30):
        try:
            with urllib.request.urlopen(url, timeout=1):
                break
        except OSError:
            if attempt == 29:
                raise
            time.sleep(0.2)
    if browser_pids(number):
        if status(number)["state"] == "streaming":
            print(f"Monitor {number} ya abierto; no se duplica la ventana.")
            place_window(number)
            return
        close_browser(number)
    profile = profile_for(number)
    profile.mkdir(parents=True, exist_ok=True)
    with (profile.parent / f"chrome-monitor-{number}.log").open("a") as log:
        browser = subprocess.Popen(
            [
                "/usr/bin/google-chrome",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--start-fullscreen",
                f"--window-position={x},{y}",
                f"--window-size={width},{height}",
                f"--app={url}",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(30):
        if browser_pids(number):
            place_window(number)
            return
        if browser.poll() is not None:
            raise RuntimeError(f"Chrome no pudo abrir el visor {number}; revisar su registro.")
        time.sleep(0.1)
    raise RuntimeError(f"No se pudo confirmar la apertura del visor {number}.")


def main():
    parser = argparse.ArgumentParser()
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--monitor", type=int, choices=(1, 2), default=1)
    choice.add_argument("--both", action="store_true")
    choice.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp/opencode"))
    with (runtime / "spacedesk-launch.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.stop:
            subprocess.run(["systemctl", "--user", "stop", "spacedesk-monitor@1",
                            "spacedesk-monitor@2"], check=True)
            close_browser(1)
            close_browser(2)
            return
        for number in ([1, 2] if args.both else [args.monitor]):
            open_monitor(number)
            print(json.dumps(wait_for_stream(number), ensure_ascii=False))


if __name__ == "__main__":
    main()
