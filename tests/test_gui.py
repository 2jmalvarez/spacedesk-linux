"""Optional real-X11 GTK smoke test. No Windows connections or saved changes."""
import os
import sys
import time
import subprocess
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.environ.get("SPACEDESK_TEST_GUI") == "1", "Opt-in real-display GTK test")
class GuiTests(unittest.TestCase):
    def test_cold_import_selects_gtk3_and_gdk3(self):
        result = subprocess.run([sys.executable, "-B", "-c",
                                 "from spacedesk_linux.gui import Gtk, Gdk; "
                                 "assert Gtk.get_major_version() == 3"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PyGIWarning", result.stderr)

    def test_panel_map_quantity_and_resolution(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        from spacedesk_linux import config
        from spacedesk_linux.displays import detect
        from spacedesk_linux.gui import ControlWindow

        app = Gtk.Application()
        app.register()
        displays = detect()
        errors = []
        previous_hook = sys.excepthook
        sys.excepthook = lambda *args: errors.append(args)
        window = None
        try:
            with patch("spacedesk_linux.gui.Controller.statuses", return_value={}):
                window = ControlWindow(app, config.default_config(displays, "192.0.2.10"), displays)
                for _ in range(15):
                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
                    time.sleep(0.02)
                self.assertEqual(len(window.map.get_children()), len(displays))
                self.assertEqual(window.count.get_value_as_int(), min(2, len(displays)))
                for count in range(1, len(displays) + 1):
                    window.count.set_value(count)
                    self.assertEqual(sum(r["check"].get_active() for r in window.rows.values()), count)
                row = window.rows[displays[0].connector]
                width, height = displays[0].modes[-1]
                row["resolution"].set_active_id(f"{width}x{height}")
                screen = window.read_settings()["screens"][0]
                self.assertEqual((screen["width"], screen["height"]), (width, height))
                with patch.object(window, "refresh_displays") as refresh:
                    window.monitors_changed()
                    first_timer = window.hotplug_timer
                    window.monitors_changed()
                    self.assertNotEqual(first_timer, window.hotplug_timer)
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline:
                        while Gtk.events_pending():
                            Gtk.main_iteration_do(False)
                        time.sleep(0.02)
                    refresh.assert_called_once_with()
                self.assertEqual(errors, [])
        finally:
            if window is not None:
                window.destroy()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            sys.excepthook = previous_hook
