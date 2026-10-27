import unittest
from pathlib import Path


class PackagingTests(unittest.TestCase):
    def test_environment_file_path_is_not_literal_quoted(self):
        root = Path(__file__).parents[1]
        unit = (root / "packaging/spacedesk-linux@.service.in").read_text()
        rendered = unit.replace("@CONFIG_DIR@", "/example/config").replace("@APP_DIR@", "/example/app")
        self.assertIn("EnvironmentFile=/example/config/runtime/%i.env\n", rendered)
        self.assertNotIn('EnvironmentFile="', rendered)
        self.assertIn("TimeoutStopSec=5\n", rendered)

    def test_no_personal_checkout_or_server_address_in_sources(self):
        root = Path(__file__).parents[1]
        for directory in (root / "src", root / "packaging", root / "scripts"):
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in (".py", ".in", ".sh"):
                    text = path.read_text()
                    self.assertNotRegex(text, r'/(?:home|Users)/[^/\s"\']+/', str(path))
                    self.assertNotRegex(text, r'(?<![\d.])192\.168\.\d{1,3}\.\d{1,3}(?![\d.])', str(path))
