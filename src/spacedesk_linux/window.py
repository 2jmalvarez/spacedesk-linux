"""Position one existing browser window. Runs in its own GTK main thread."""
import argparse
import re
import subprocess
import time


def place(pids, x, y, width, height):
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkX11", "3.0")
    from gi.repository import Gdk, GdkX11

    window_id = None
    for _ in range(40):
        root = subprocess.check_output(["xprop", "-root", "_NET_CLIENT_LIST"], text=True)
        for candidate in re.findall(r"0x[0-9a-fA-F]+", root):
            result = subprocess.run(["xprop", "-id", candidate, "_NET_WM_PID"],
                                    capture_output=True, text=True)
            match = re.search(r"= (\d+)", result.stdout)
            if match and int(match[1]) in pids:
                window_id = int(candidate, 16)
                break
        if window_id is not None:
            break
        time.sleep(0.1)
    if window_id is None:
        raise RuntimeError("No se encontro la ventana del visor.")
    display = Gdk.Display.get_default()
    monitor = next((i for i in range(display.get_n_monitors())
                    if (display.get_monitor(i).get_geometry().x,
                        display.get_monitor(i).get_geometry().y) == (x, y)), None)
    if monitor is None:
        raise RuntimeError("El monitor seleccionado ya no esta disponible.")
    window = GdkX11.X11Window.foreign_new_for_display(display, window_id)
    window.unmaximize()
    window.move_resize(x + 10, y + 40, max(100, width - 20), max(100, height - 80))
    window.fullscreen_on_monitor(monitor)
    window.focus(Gdk.CURRENT_TIME)
    display.sync()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pids", required=True)
    parser.add_argument("geometry", nargs=4, type=int)
    args = parser.parse_args()
    place({int(pid) for pid in args.pids.split(",")}, *args.geometry)
