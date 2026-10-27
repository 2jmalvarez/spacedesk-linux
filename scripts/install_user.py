#!/usr/bin/env python3
"""Reproducible user-only installation. Does not install packages or use sudo."""
import argparse
import datetime
import os
import re
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", help="IP/nombre de Windows, guardado solo en la configuracion local")
    parser.add_argument("--migrate-legacy", action="store_true",
                        help="Detener y respaldar la instalacion standalone anterior")
    args = parser.parse_args()
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("GdkX11", "3.0")
    for executable in ("systemctl", "xrandr", "xprop"):
        if shutil.which(executable) is None:
            raise SystemExit(f"Falta {executable}; consulta README.md.")
    if not any(shutil.which(name) for name in ("google-chrome", "chromium", "chromium-browser")):
        raise SystemExit("Falta Google Chrome o Chromium.")
    home = Path.home()
    root = Path(__file__).resolve().parents[1]
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
    data = data_home / "spacedesk-linux"
    app = data / "app"
    config = config_home / "spacedesk-linux"
    units = config_home / "systemd/user"
    applications = data_home / "applications"
    executable = home / ".local/bin/spacedesk-linux"
    legacy = home / ".local/share/spacedesk-linux/launch.py"
    old_unit = home / ".config/systemd/user/spacedesk-monitor@.service"
    backup = state_home / "spacedesk-linux/backups" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    host = args.host
    if args.migrate_legacy:
        candidates = [data / name for name in ("launch.py", "spacedesk_client.py", "test_client.py",
                                               "test_protocol.py", "INSTALLATION.md")]
        candidates += [old_unit, home / ".config/spacedesk/monitor-1.env", home / ".config/spacedesk/monitor-2.env"]
        candidates += list(applications.glob("spacedesk-*.desktop"))
        for file in candidates:
            if file.is_file():
                destination = backup / file.relative_to(home)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, destination)
        if host is None and old_unit.exists():
            match = re.search(r"^Environment=SPACEDESK_DRIVER=([^\s]+)$", old_unit.read_text(), re.M)
            if match:
                host = match[1]
        if legacy.exists() and "MONITORS =" in legacy.read_text():
            subprocess.run(["/usr/bin/python3", str(legacy), "--stop"], check=True)
        for desktop in applications.glob("spacedesk-*.desktop"):
            if desktop.is_file() and str(legacy) in desktop.read_text():
                desktop.unlink()
    for directory in (app, config / "runtime", units, applications, executable.parent):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "src/spacedesk_linux", app / "spacedesk_linux", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / name, data / name)
    bootstrap = ("#!/usr/bin/python3\nimport sys\n"
                 f"sys.path.insert(0, {str(app)!r})\n"
                 "from spacedesk_linux.__main__ import main\n"
                 "if __name__ == '__main__':\n"
                 "    try:\n        raise SystemExit(main())\n"
                 "    except (RuntimeError, ValueError, OSError) as error:\n"
                 "        raise SystemExit(str(error))\n")
    executable.write_text(bootstrap)
    executable.chmod(0o755)
    values = {"@APP_DIR@": str(app), "@CONFIG_DIR@": str(config), "@EXECUTABLE@": str(executable)}
    for filename, directory in (("spacedesk-linux@.service", units),
                                ("spacedesk-linux.desktop", applications),
                                ("spacedesk-linux-stop.desktop", applications)):
        text = (root / "packaging" / (filename + ".in")).read_text()
        for key, value in values.items():
            if any(char in value for char in ('"', '\n', '\r', '%')):
                raise SystemExit("Ruta no compatible con las plantillas de instalacion.")
            text = text.replace(key, value)
        (directory / filename).write_text(text)
    if args.migrate_legacy:
        # Compatibility with the two commands already supplied to the user.
        legacy.write_text("#!/usr/bin/python3\nimport os, sys\n"
                          f"executable = {str(executable)!r}\n"
                          "command = 'stop' if '--stop' in sys.argv else 'connect' if '--both' in sys.argv else 'gui'\n"
                          "os.execv(executable, [executable, command])\n")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    command = [str(executable), "init"]
    # Never overwrite an existing user's host/selection during reinstallation.
    if host and not (config / "config.json").exists():
        command += ["--host", host]
    subprocess.run(command, check=True)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=True)
    print(f"Instalado: {executable}\nCodigo fuente: {root}\nConfiguracion privada: {config}")
    if args.migrate_legacy:
        print(f"Respaldo de la instalacion anterior: {backup}")


if __name__ == "__main__":
    main()
