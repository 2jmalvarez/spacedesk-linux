import tempfile
import unittest
import threading
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from spacedesk_linux import config, controller
from spacedesk_linux.displays import Display


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.display = Display("HDMI-TEST", 0, 0, 1920, 1080)
        self.config = config.default_config([self.display], "192.0.2.10")
        self.screen = self.config["screens"][0]

    def test_environment_uses_config_and_monitor_resolution(self):
        self.screen.update(width=1280, height=720)
        text = controller.environment(self.config, self.screen, self.display)
        self.assertIn("SPACEDESK_WIDTH=1280\n", text)
        self.assertIn("SPACEDESK_HEIGHT=720\n", text)
        self.assertIn("SPACEDESK_AUTORECONNECT=0\n", text)
        self.assertIn("SPACEDESK_HTTP_HOST=127.0.0.1\n", text)

    def test_new_viewer_profile_disables_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(controller, "CACHE_DIR", Path(directory)), \
                    patch.object(controller, "browser_pids", return_value=[]):
                controller.configure_browser_profile(self.screen)
                path = controller.profile(self.screen) / "Default/Preferences"
                self.assertIs(json.loads(path.read_text())["translate"]["enabled"], False)
                self.assertEqual(list(path.parent.iterdir()), [path])

    def test_profile_translation_setting_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            normal = root / "normal-chrome/Preferences"
            normal.parent.mkdir()
            normal.write_text('{"translate":{"enabled":true}}')
            with patch.object(controller, "CACHE_DIR", root / "isolated"), \
                    patch.object(controller, "browser_pids", return_value=[]):
                path = controller.profile(self.screen) / "Default/Preferences"
                path.parent.mkdir(parents=True)
                original = {"session": {"restore_on_startup": 1},
                            "translate": {"enabled": True, "recent_target": "es"}}
                path.write_text(json.dumps(original))
                controller.configure_browser_profile(self.screen)
                updated = json.loads(path.read_text())
            self.assertEqual(updated["session"], original["session"])
            self.assertEqual(updated["translate"], {"enabled": False, "recent_target": "es"})
            self.assertIs(json.loads(normal.read_text())["translate"]["enabled"], True)

    def test_running_browser_profile_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(controller, "CACHE_DIR", Path(directory)), \
                    patch.object(controller, "browser_pids", return_value=[123]):
                with self.assertRaisesRegex(RuntimeError, "cerrado"):
                    controller.configure_browser_profile(self.screen)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_profile_preferences_are_not_overwritten(self):
        for contents in ('{invalid', '[]', '{"translate":false}'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as directory:
                with patch.object(controller, "CACHE_DIR", Path(directory)), \
                        patch.object(controller, "browser_pids", return_value=[]):
                    path = controller.profile(self.screen) / "Default/Preferences"
                    path.parent.mkdir(parents=True)
                    path.write_text(contents)
                    with self.assertRaisesRegex(RuntimeError, "No se modificó"):
                        controller.configure_browser_profile(self.screen)
                    self.assertEqual(path.read_text(), contents)

    def test_detect_chrome_rewritten_cmdline_and_ignore_renderers(self):
        process = MagicMock()
        process.name = "123"
        expected = f"--user-data-dir={controller.profile(self.screen)}"
        process.__truediv__.return_value.read_bytes.return_value = (
            f"/opt/google/chrome/chrome {expected} --app=http://127.0.0.1/\0".encode())
        with patch.object(Path, "iterdir", return_value=[process]):
            self.assertEqual(controller.browser_pids(self.screen), [123])
        process.__truediv__.return_value.read_bytes.return_value = (
            f"/opt/google/chrome/chrome {expected} --type=renderer\0".encode())
        with patch.object(Path, "iterdir", return_value=[process]):
            self.assertEqual(controller.browser_pids(self.screen), [])

    def test_missing_destination_fails_before_services_are_changed(self):
        with patch.object(controller.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Falta el monitor"):
                controller.Controller(self.config, []).connect()
        run.assert_not_called()

    def test_existing_streaming_window_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"{self.screen['id']}.env").write_text(
                controller.environment(self.config, self.screen, self.display))
            app = controller.Controller(self.config, [self.display])
            with patch.object(controller, "RUNTIME_CONFIG", root), \
                    patch.object(controller, "status", return_value={"state": "streaming"}), \
                    patch.object(controller, "browser_pids", return_value=[123]), \
                    patch.object(controller.subprocess, "run"), \
                    patch.object(controller.subprocess, "Popen") as popen, \
                    patch.object(app, "_place") as place:
                app._connect_screen(self.screen, self.display, "google-chrome")
            popen.assert_not_called()
            place.assert_called_once_with(self.screen, self.display)

    def test_zero_enabled_stops_instead_of_launching(self):
        self.screen["enabled"] = False
        app = controller.Controller(self.config, [self.display])
        with patch.object(app, "stop") as stop, patch.object(app, "statuses", return_value={}):
            app.connect()
        stop.assert_called_once_with()

    def test_stop_notifies_multiple_services_in_parallel(self):
        second = Display("HDMI-SECOND", 1920, 0, 1920, 1080)
        config_value = config.default_config([self.display, second], "192.0.2.10")
        app = controller.Controller(config_value)
        barrier = threading.Barrier(2)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(controller, "RUNTIME_CONFIG", Path(directory)), \
                    patch.object(controller, "operation_lock", return_value=MagicMock()), \
                    patch.object(app, "_stop_screen", side_effect=lambda screen: barrier.wait(timeout=2)) as stop:
                app.stop()
        self.assertEqual(stop.call_count, 2)

    def test_port_probe_allows_time_wait_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f"{self.screen['id']}.env").write_text(
                controller.environment(self.config, self.screen, self.display))
            app = controller.Controller(self.config, [self.display])
            factory = MagicMock()
            probe = factory.return_value.__enter__.return_value
            states = [{"state": "stopped"}, {"state": "streaming"}, {"state": "streaming"}]
            with patch.object(controller, "RUNTIME_CONFIG", root), \
                    patch.object(controller, "status", side_effect=states), \
                    patch.object(controller, "browser_pids", return_value=[123]), \
                    patch.object(controller.socket, "socket", factory), \
                    patch.object(controller.subprocess, "run"), patch.object(app, "_place"):
                app._connect_screen(self.screen, self.display, "google-chrome")
            probe.setsockopt.assert_called_once_with(controller.socket.SOL_SOCKET,
                                                      controller.socket.SO_REUSEADDR, 1)
            probe.bind.assert_called_once_with(("127.0.0.1", self.screen["port"]))
