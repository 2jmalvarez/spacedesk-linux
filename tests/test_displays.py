import os
import subprocess
import unittest
from unittest.mock import patch

from spacedesk_linux import displays


OUTPUT = """HDMI-1 connected primary 1920x1080+0+0 (normal)
   1920x1080     60.00*+
HDMI-2 connected 1366x768+1920+0 (normal)
   1366x768      60.00*+
"""


class DetectionTests(unittest.TestCase):
    def test_only_connected_outputs_with_positive_geometry_are_listed(self):
        output = OUTPUT + """HDMI-OLD disconnected (normal)
HDMI-OFF connected (normal)
   1920x1080     60.00+
HDMI-ZERO connected 0x0+0+0 (normal)
HDMI-FLAT connected 1920x0+0+0 (normal)
HDMI-NARROW connected 0x1080+0+0 (normal)
"""
        self.assertEqual([d.connector for d in displays.parse_xrandr(output)],
                         ["HDMI-1", "HDMI-2"])

    def test_x11_and_wayland_with_xwayland_use_real_monitor_query(self):
        for session in ("x11", "wayland"):
            with self.subTest(session=session), \
                    patch.dict(os.environ, {"XDG_SESSION_TYPE": session, "DISPLAY": ":1"}), \
                    patch.object(displays.subprocess, "run", return_value=
                                 subprocess.CompletedProcess([], 0, OUTPUT)) as run:
                found = displays.detect()
                self.assertEqual([(d.connector, d.x, d.width) for d in found],
                                 [("HDMI-1", 0, 1920), ("HDMI-2", 1920, 1366)])
                self.assertEqual(found[0].native, (1920, 1080))
                run.assert_called_once_with(["xrandr", "--query"], capture_output=True,
                                            text=True, check=True, timeout=5)

    def test_wayland_without_xwayland_fails_before_running_commands(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ""}), \
                patch.object(displays.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "XWayland"):
                displays.detect()
            run.assert_not_called()

    def test_unavailable_x_server_is_not_silently_accepted(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":1"}), \
                patch.object(displays.subprocess, "run", side_effect=
                             subprocess.CalledProcessError(1, ["xrandr", "--query"])):
            with self.assertRaises(subprocess.CalledProcessError):
                displays.detect()

    def test_empty_query_does_not_invent_monitors(self):
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":1"}), \
                patch.object(displays.subprocess, "run", return_value=
                             subprocess.CompletedProcess([], 0, "")):
            with self.assertRaisesRegex(RuntimeError, "monitores"):
                displays.detect()
