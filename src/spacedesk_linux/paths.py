import os
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "spacedesk-linux"
CONFIG_FILE = CONFIG_DIR / "config.json"
RUNTIME_CONFIG = CONFIG_DIR / "runtime"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "spacedesk-linux"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "spacedesk-linux"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", CACHE_DIR / "runtime"))
