#!/usr/bin/env python3
"""Remove this app's installed code, retaining configuration/cache/backups."""
import os
import shutil
import subprocess
from pathlib import Path

home = Path.home()
data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
executable = home / ".local/bin/spacedesk-linux"
if executable.exists():
    subprocess.run([str(executable), "stop"], check=True)
for filename in ("spacedesk-linux.desktop", "spacedesk-linux-stop.desktop"):
    (data_home / "applications" / filename).unlink(missing_ok=True)
(config_home / "systemd/user/spacedesk-linux@.service").unlink(missing_ok=True)
app = data_home / "spacedesk-linux/app"
if app.exists():
    shutil.rmtree(app)
executable.unlink(missing_ok=True)
legacy = home / ".local/share/spacedesk-linux/launch.py"
if legacy.is_file() and str(executable) in legacy.read_text() and "os.execv" in legacy.read_text():
    legacy.unlink()
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
print("Aplicacion desinstalada. Configuracion, perfiles y respaldos conservados.")
