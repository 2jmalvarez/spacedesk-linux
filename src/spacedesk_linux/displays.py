"""Discover active physical X11 displays without changing their configuration."""
import os
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class Display:
    connector: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False
    modes: list = field(default_factory=list)
    preferred: tuple | None = None

    @property
    def native(self):
        return self.preferred or (self.width, self.height)


def parse_xrandr(text):
    displays = []
    current = None
    for line in text.splitlines():
        if line and not line[0].isspace():
            current = None
            match = re.match(r"^(\S+) connected (.*)$", line)
            if not match:
                continue
            geometry = re.search(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", match[2])
            if not geometry:
                continue
            width, height, x, y = map(int, geometry.groups())
            current = Display(match[1], x, y, width, height, "primary" in match[2].split())
            displays.append(current)
        elif current is not None:
            mode = re.match(r"\s+(\d+)x(\d+)\s+(.+)$", line)
            if mode:
                size = (int(mode[1]), int(mode[2]))
                if size not in current.modes:
                    current.modes.append(size)
                if "+" in mode[3]:
                    current.preferred = size
    return sorted(displays, key=lambda display: (display.x, display.y, display.connector))


def detect():
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        raise RuntimeError("Esta version necesita una sesion X11; Wayland aun no esta soportado.")
    result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True,
                            check=True, timeout=5)
    displays = parse_xrandr(result.stdout)
    if not displays:
        raise RuntimeError("No se encontraron monitores X11 activos.")
    return displays
