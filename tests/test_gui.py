"""Optional real-X11 GTK smoke test. No Windows connections or saved changes."""
import os
import sys
import time
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import Mock
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
                actions = window.connection_button.get_parent().get_children()
                self.assertEqual([button.get_label() for button in actions],
                                 ["Guardar configuración", "Conectar"])
                self.assertFalse(hasattr(window, "stop_button"))
                self.assertFalse(hasattr(window, "connect_button"))
                with patch.object(window, "connect_all") as connect, \
                        patch.object(window, "disconnect_all") as disconnect:
                    window.show_statuses({screen["id"]: {"state": "stopped"}})
                    window.connection_button.emit("clicked")
                    connect.assert_called_once_with()
                    disconnect.assert_not_called()
                    window.show_statuses({screen["id"]: {"state": "streaming", "width": 1920, "height": 1080},
                                          "partial-error": {"state": "disconnected"}})
                    self.assertEqual(window.connection_button.get_label(), "Desconectar")
                    window.connection_button.emit("clicked")
                    disconnect.assert_called_once_with()
                    window.set_busy(True)
                    self.assertFalse(window.connection_button.get_sensitive())
                    window.connection_button.emit("clicked")
                    disconnect.assert_called_once_with()
                    window.set_busy(False)
                    window.show_statuses({screen["id"]: {"state": "disconnected"}})
                    self.assertEqual(window.connection_button.get_label(), "Conectar")
                    window.connection_states_known = False
                    window.update_connection_button()
                    self.assertFalse(window.connection_button.get_sensitive())
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

    def test_old_status_poll_cannot_overwrite_new_operation_state(self):
        from spacedesk_linux import config
        from spacedesk_linux.displays import Display
        from spacedesk_linux.gui import ControlWindow
        pending, ready = [], threading.Event()
        window = SimpleNamespace(closed=False, busy=False, polling=False,
                                 status_generation=0, show_statuses=Mock(),
                                 config=config.default_config([Display("TEST", 0, 0, 1920, 1080)]))
        def defer(callback):
            pending.append(callback)
            ready.set()
        with patch("spacedesk_linux.gui.Controller.statuses", return_value={}), \
                patch("spacedesk_linux.gui.GLib.idle_add", side_effect=defer):
            self.assertTrue(ControlWindow.poll_status(window))
            self.assertTrue(ready.wait(2))
            window.status_generation += 1
            pending[0]()
        self.assertFalse(window.polling)
        window.show_statuses.assert_not_called()
