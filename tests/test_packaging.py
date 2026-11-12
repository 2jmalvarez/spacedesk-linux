import unittest
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from spacedesk_linux import __version__


class PackagingTests(unittest.TestCase):
    def test_version_uses_package_attribute(self):
        root = Path(__file__).parents[1]
        metadata = (root / "pyproject.toml").read_text()
        self.assertIn('dynamic = ["version"]', metadata)
        self.assertIn('version = {attr = "spacedesk_linux.__version__"}', metadata)
        result = subprocess.run([sys.executable, "-B", "-m", "spacedesk_linux", "--version"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip().split()[-1], __version__)

    @unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb is required")
    def test_debian_package_build_and_extracted_payload(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            result = subprocess.run([sys.executable, "-B", str(root / "scripts/build_deb.py"),
                                     "--output", str(directory)], capture_output=True, text=True, check=True)
            package = directory / f"spacedesk-linux_{__version__}_all.deb"
            self.assertTrue(package.is_file(), result.stdout)
            for field, expected in (("Package", "spacedesk-linux"), ("Version", __version__),
                                    ("Architecture", "all")):
                value = subprocess.check_output(["dpkg-deb", "--field", str(package), field], text=True)
                self.assertEqual(value.strip(), expected)
            dependencies = subprocess.check_output(["dpkg-deb", "--field", str(package), "Depends"], text=True)
            for dependency in ("python3 (>= 3.10)", "python3-gi", "gir1.2-gtk-3.0",
                               "x11-xserver-utils", "x11-utils", "systemd"):
                self.assertIn(dependency, dependencies)
            extracted = directory / "extracted"
            subprocess.run(["dpkg-deb", "--extract", str(package), str(extracted)], check=True)
            app = extracted / "usr/lib/spacedesk-linux"
            self.assertEqual(runpy.run_path(str(app / "spacedesk_linux/__init__.py"))["__version__"], __version__)
            self.assertFalse(list(extracted.rglob("*.pyc")))
            self.assertFalse(list(extracted.rglob("__pycache__")))
            launcher = extracted / "usr/bin/spacedesk-linux"
            self.assertEqual(launcher.stat().st_mode & 0o777, 0o755)
            self.assertIn("'/usr/lib/spacedesk-linux'", launcher.read_text())
            env = dict(os.environ, PYTHONPATH=str(app), PYTHONDONTWRITEBYTECODE="1")
            version = subprocess.check_output([sys.executable, "-B", str(launcher), "--version"],
                                              cwd=directory, env=env, text=True)
            self.assertEqual(version.strip().split()[-1], __version__)
            unit = (extracted / "usr/lib/systemd/user/spacedesk-linux@.service").read_text()
            self.assertIn("EnvironmentFile=%E/spacedesk-linux/runtime/%i.env", unit)
            self.assertIn('ExecStart=/usr/bin/python3 "/usr/lib/spacedesk-linux/spacedesk_linux/bridge.py"', unit)
            self.assertNotIn("[Install]", unit)  # Never autostart a Windows connection.
            for path in extracted.rglob("*"):
                if path.is_file():
                    self.assertNotIn("@APP_DIR@", path.read_text())
                    self.assertNotIn("@CONFIG_DIR@", path.read_text())
                    self.assertNotIn("@EXECUTABLE@", path.read_text())
            for filename in ("spacedesk-linux.desktop", "spacedesk-linux-stop.desktop"):
                desktop = extracted / "usr/share/applications" / filename
                self.assertIn('Exec="/usr/bin/spacedesk-linux"', desktop.read_text())
                if shutil.which("desktop-file-validate"):
                    subprocess.run(["desktop-file-validate", str(desktop)], check=True)
            for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
                self.assertTrue((extracted / "usr/share/doc/spacedesk-linux" / filename).is_file())

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
