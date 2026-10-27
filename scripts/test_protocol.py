#!/usr/bin/env python3
"""Bounded protocol check: counts JPEG data without saving desktop contents."""
import argparse
import concurrent.futures
import importlib.util
import json
import socket
import struct
import time
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from spacedesk_linux import config as settings
from spacedesk_linux.controller import Controller, device_name
from spacedesk_linux.displays import detect


def probe(config, screen, display, seconds, delay):
    time.sleep(delay)
    spec = importlib.util.spec_from_file_location(
        "probe_" + screen["id"], Path(__file__).parents[1] / "src/spacedesk_linux/bridge.py"
    )
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    client.DEVICE_NAME = device_name(screen)
    client.REQ_WIDTH, client.REQ_HEIGHT = settings.resolution(screen, display)
    client.JPEG_QUALITY = config["quality"]
    result = {"monitor": screen["connector"], "tiles": 0, "bytes": 0, "pings": 0,
              "visibility": [], "closed_by_server": False}
    sock = socket.create_connection((config["host"], 28252), timeout=5)
    sock.settimeout(0.5)
    start = time.monotonic()
    fragments = 0
    pending = bytearray()
    try:
        sock.sendall(client.build_handshake() + client.FLOW_ACK)
        while time.monotonic() - start < seconds:
            try:
                data = sock.recv(262144)
            except socket.timeout:
                continue
            if not data:
                result["closed_by_server"] = True
                break
            pending.extend(data)
            while len(pending) >= 128:
                kind, size = struct.unpack_from("<II", pending)
                if size > 32 * 1024 * 1024:
                    raise ValueError("invalid payload size")
                if len(pending) < 128 + size:
                    break
                header = bytes(pending[:128])
                payload = bytes(pending[128:128 + size])
                del pending[:128 + size]
                if kind == 1:
                    result["pings"] += 1
                    sock.sendall(client.build_pong())
                elif kind == 3:
                    result["visibility"].append(struct.unpack_from("<II", header, 8))
                    sock.sendall(client.FLOW_ACK)
                elif kind == 2:
                    if payload[:2] != b"\xff\xd8":
                        raise ValueError("non-JPEG video payload")
                    result["tiles"] += 1
                    result["bytes"] += size
                    result["resolution"] = struct.unpack_from("<II", header, 8)
                    if struct.unpack_from("<I", header, 64)[0] == 1:
                        fragments += 1
                        if fragments == 4:
                            sock.sendall(client.FLOW_ACK)
                            fragments = 0
                    else:
                        fragments = 0
                        sock.sendall(client.FLOW_ACK)
                elif kind == 8:
                    result["closed_by_server"] = True
                    return result
    except Exception as error:
        result["error"] = str(error)
    finally:
        result["seconds"] = round(time.monotonic() - start, 2)
        try:
            packet = bytearray(128)
            struct.pack_into("<I", packet, 0, 8)
            sock.sendall(packet)
        except OSError:
            pass
        sock.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=12)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error("--seconds debe estar entre 1 y 600")
    config = settings.load()
    if config is None:
        parser.error("Primero guardar la configuracion desde la app.")
    displays = detect()
    settings.validate(config, displays, connecting=True)
    screens = [s for s in config["screens"] if s["enabled"]]
    if not screens:
        parser.error("No hay pantallas seleccionadas.")
    if any(s["state"] in {"streaming", "waiting", "connecting"}
           for s in Controller(config).statuses().values()):
        parser.error("Cerrar primero los visores; la prueba no debe competir por sus identidades.")
    by_connector = {d.connector: d for d in displays}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(probe, config, screen, by_connector[screen["connector"]],
                                   args.seconds + 3 * (len(screens) - 1 - i), 3 * i)
                   for i, screen in enumerate(screens)]
        results = [future.result() for future in futures]
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(r["tiles"] and not r["closed_by_server"] and "error" not in r
                              for r in results) else 1)
