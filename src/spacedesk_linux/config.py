"""Single persistent configuration; no host address or topology in source code."""
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from .paths import CONFIG_FILE


def default_config(displays, host=""):
    preferred = sorted(displays, key=lambda d: (-d.native[0] * d.native[1], d.x, d.y))[:2]
    selected = {d.connector for d in preferred}
    return {"version": 1, "host": host, "quality": 50,
            "screens": [{"id": uuid.uuid4().hex[:12], "connector": d.connector,
                         "enabled": d.connector in selected, "width": None, "height": None,
                         "port": 8091 + i} for i, d in enumerate(displays)]}


def load(path=CONFIG_FILE):
    try:
        with Path(path).open() as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return None
    validate(value)
    return value


def reconcile(config, displays):
    """Keep connector assignments; newly found monitors are disabled by default."""
    config = json.loads(json.dumps(config))
    known = {s["connector"] for s in config["screens"]}
    ports = {s["port"] for s in config["screens"]}
    for display in displays:
        if display.connector not in known:
            port = 8091
            while port in ports:
                port += 1
            ports.add(port)
            config["screens"].append({"id": uuid.uuid4().hex[:12],
                                      "connector": display.connector, "enabled": False,
                                      "width": None, "height": None, "port": port})
    return config


def validate(config, displays=None, connecting=False):
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Version de configuracion no soportada.")
    host = config.get("host", "")
    if not isinstance(host, str) or (host and not re.fullmatch(r"[A-Za-z0-9_.-]{1,253}", host)):
        raise ValueError("IP o nombre de Windows invalido (IPv4/nombre DNS, sin espacios).")
    if connecting and not host:
        raise ValueError("Ingresa la IP de Windows.")
    quality = config.get("quality")
    if type(quality) is not int or not 1 <= quality <= 100:
        raise ValueError("La calidad debe estar entre 1 y 100.")
    screens = config.get("screens")
    if not isinstance(screens, list):
        raise ValueError("Lista de pantallas invalida.")
    ids, ports, connectors = set(), set(), set()
    available = {d.connector for d in displays} if displays is not None else None
    for screen in screens:
        key, port, connector = screen.get("id"), screen.get("port"), screen.get("connector")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,40}", key) or key in ids:
            raise ValueError("Identidad de pantalla invalida o duplicada.")
        if type(port) is not int or not 1024 <= port <= 65535 or port in ports:
            raise ValueError("Puerto de visor invalido o duplicado.")
        if not isinstance(connector, str) or not connector or connector in connectors:
            raise ValueError("Monitor fisico invalido o duplicado.")
        if type(screen.get("enabled")) is not bool:
            raise ValueError("Seleccion de pantalla invalida.")
        width, height = screen.get("width"), screen.get("height")
        if (width, height) != (None, None):
            if not all(type(n) is int and 320 <= n <= 8192 for n in (width, height)):
                raise ValueError("Resolucion invalida (320 a 8192 pixeles por dimension).")
        if connecting and screen["enabled"] and available is not None and connector not in available:
            raise ValueError(f"Falta el monitor {connector}; no se reemplazara por otro.")
        ids.add(key)
        ports.add(port)
        connectors.add(connector)
    return config


def save(config, path=CONFIG_FILE):
    validate(config)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(config, stream, indent=2)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolution(screen, display):
    return display.native if screen["width"] is None else (screen["width"], screen["height"])
