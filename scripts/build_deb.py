#!/usr/bin/env python3
"""Build an architecture-independent Debian package without root or downloads."""
import argparse
import re
import runpy
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = "/usr/lib/spacedesk-linux"


def build(output):
    if shutil.which("dpkg-deb") is None:
        raise RuntimeError("Falta dpkg-deb; instala el paquete dpkg para construir el .deb.")
    version = runpy.run_path(str(ROOT / "src/spacedesk_linux/__init__.py"))["__version__"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("La version del paquete debe tener formato X.Y.Z.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"spacedesk-linux_{version}_all.deb"
    with tempfile.TemporaryDirectory(prefix="spacedesk-deb-") as temporary:
        package = Path(temporary) / "package"

        def write(name, text, mode=0o644):
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            path.chmod(mode)

        shutil.copytree(ROOT / "src/spacedesk_linux", package / APP_DIR.lstrip("/") / "spacedesk_linux",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        write("usr/bin/spacedesk-linux", "#!/usr/bin/python3\nimport sys\n"
              f"sys.path.insert(0, {APP_DIR!r})\n"
              "from spacedesk_linux.__main__ import main\n"
              "try:\n    raise SystemExit(main())\n"
              "except (RuntimeError, ValueError, OSError) as error:\n"
              "    raise SystemExit(str(error)) from error\n", 0o755)
        values = {"@APP_DIR@": APP_DIR, "@CONFIG_DIR@": "%E/spacedesk-linux",
                  "@EXECUTABLE@": "/usr/bin/spacedesk-linux"}
        for filename, directory in (("spacedesk-linux@.service", "usr/lib/systemd/user"),
                                    ("spacedesk-linux.desktop", "usr/share/applications"),
                                    ("spacedesk-linux-stop.desktop", "usr/share/applications")):
            text = (ROOT / "packaging" / (filename + ".in")).read_text()
            for key, value in values.items():
                text = text.replace(key, value)
            write(f"{directory}/{filename}", text)
        for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
            write(f"usr/share/doc/spacedesk-linux/{filename}", (ROOT / filename).read_text())
        write("DEBIAN/control", f"""Package: spacedesk-linux
Version: {version}
Section: net
Priority: optional
Architecture: all
Maintainer: spacedesk Linux contributors <noreply@github.com>
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, x11-xserver-utils, x11-utils, systemd
Recommends: xwayland
Suggests: google-chrome-stable | chromium
Homepage: https://github.com/2jmalvarez/spacedesk-linux
Description: Unofficial spacedesk monitor controller for Linux
 GTK 3 panel and per-user bridge services for X11/XWayland.
 Requires a graphical user session and a native Chrome or Chromium browser.
 The proprietary Windows spacedesk driver is not included.
""")
        # Normalize permissions independently of the builder's umask/checkout modes.
        for path in package.rglob("*"):
            path.chmod(0o755 if path.is_dir() or path == package / "usr/bin/spacedesk-linux" else 0o644)
        package.chmod(0o755)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(package), str(destination)], check=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(build(args.output))


if __name__ == "__main__":
    main()
