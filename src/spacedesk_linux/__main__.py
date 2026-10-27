import argparse
import json

from . import config as settings
from .controller import Controller
from .displays import detect


def main():
    parser = argparse.ArgumentParser(description="Control no oficial de spacedesk para Linux/X11")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui")
    commands.add_parser("connect")
    commands.add_parser("stop")
    commands.add_parser("status")
    commands.add_parser("displays")
    init = commands.add_parser("init")
    init.add_argument("--host", default=None)
    args = parser.parse_args()
    if args.command in (None, "gui"):
        from .gui import main as gui_main
        return gui_main()
    if args.command == "displays":
        from dataclasses import asdict
        print(json.dumps([asdict(d) for d in detect()], indent=2))
        return 0
    config = settings.load()
    if args.command == "init":
        displays = detect()
        first_run = config is None
        config = settings.default_config(displays, args.host or "") if first_run else settings.reconcile(config, displays)
        if args.host is not None:
            config["host"] = args.host
        settings.save(config)
        print("Configuracion guardada; seleccionados los dos monitores mas grandes." if first_run
              else "Configuracion actualizada; se conservaron las preferencias existentes.")
        return 0
    if config is None:
        raise RuntimeError("Abri la app o ejecuta spacedesk-linux init para crear la configuracion.")
    controller = Controller(config)
    if args.command == "connect":
        print(json.dumps(controller.connect(), indent=2, ensure_ascii=False))
    elif args.command == "stop":
        controller.stop()
    elif args.command == "status":
        print(json.dumps(controller.statuses(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(str(error)) from error
