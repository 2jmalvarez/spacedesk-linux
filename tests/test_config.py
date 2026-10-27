import copy
import tempfile
import unittest
from pathlib import Path

from spacedesk_linux import config
from spacedesk_linux.displays import Display, parse_xrandr


FIXTURE = """Screen 0: minimum 8 x 8, current 5206 x 1080
HDMI-0 connected primary 1920x1080+1920+0 (normal)
   1920x1080 60.00*+
   1280x720 60.00
HDMI-2-1 connected 1366x768+3840+0 (normal)
   1366x768 59.79*+
   1280x720 60.00
HDMI-A-1-3 connected 1920x1080+0+0 (normal)
   1920x1080 60.00*+
DP-0 disconnected (normal)
"""


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.displays = parse_xrandr(FIXTURE)
        self.config = config.default_config(self.displays, "192.0.2.10")

    def test_detect_three_monitors_in_physical_order(self):
        self.assertEqual([d.connector for d in self.displays],
                         ["HDMI-A-1-3", "HDMI-0", "HDMI-2-1"])
        self.assertTrue(self.displays[1].primary)
        self.assertEqual(self.displays[2].native, (1366, 768))

    def test_select_two_largest_including_primary(self):
        selected = [s["connector"] for s in self.config["screens"] if s["enabled"]]
        self.assertEqual(selected, ["HDMI-A-1-3", "HDMI-0"])
        self.assertFalse(self.config["screens"][2]["enabled"])

    def test_negative_coordinates_and_native_preferred_mode(self):
        display = parse_xrandr("DP-1 connected 1280x720-1920-100 (normal)\n"
                               "   1920x1080 60.00+\n   1280x720 60.00*\n")[0]
        self.assertEqual((display.x, display.y), (-1920, -100))
        self.assertEqual(display.native, (1920, 1080))

    def test_screen_count_is_not_hardcoded(self):
        for number in (1, 2, 3):
            value = copy.deepcopy(self.config)
            for index, screen in enumerate(value["screens"]):
                screen["enabled"] = index < number
            config.validate(value, self.displays, connecting=True)
            self.assertEqual(sum(s["enabled"] for s in value["screens"]), number)

    def test_unplug_does_not_reassign_destination(self):
        reduced = self.displays[1:]
        value = config.reconcile(self.config, reduced)
        self.assertEqual(value["screens"], self.config["screens"])
        with self.assertRaisesRegex(ValueError, "Falta el monitor HDMI-A-1-3"):
            config.validate(value, reduced, connecting=True)

    def test_new_monitor_is_disabled_and_existing_identity_preserved(self):
        new = Display("DP-NEW", -2560, 0, 2560, 1440)
        value = config.reconcile(self.config, [new] + list(reversed(self.displays)))
        self.assertEqual(value["screens"][:3], self.config["screens"])
        self.assertFalse(value["screens"][3]["enabled"])
        config.validate(value)

    def test_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config.save(self.config, path)
            self.assertEqual(config.load(path), self.config)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_duplicate_ports_and_connectors_rejected(self):
        for key in ("port", "connector", "id"):
            value = copy.deepcopy(self.config)
            value["screens"][1][key] = value["screens"][0][key]
            with self.assertRaises(ValueError):
                config.validate(value)

    def test_host_cannot_inject_environment_settings(self):
        self.config["host"] = "host\nSPACEDESK_NAME=wrong"
        with self.assertRaises(ValueError):
            config.validate(self.config)

    def test_native_and_requested_resolution(self):
        screen = self.config["screens"][0]
        self.assertEqual(config.resolution(screen, self.displays[0]), (1920, 1080))
        screen.update(width=1280, height=720)
        self.assertEqual(config.resolution(screen, self.displays[0]), (1280, 720))

    def test_invalid_resolution_and_schema_rejected(self):
        for width, height in ((None, 1080), (True, 1080), (0, 1080), (90000, 1080)):
            value = copy.deepcopy(self.config)
            value["screens"][0].update(width=width, height=height)
            with self.assertRaises(ValueError):
                config.validate(value)
        with self.assertRaises(ValueError):
            config.validate({"version": 99})
