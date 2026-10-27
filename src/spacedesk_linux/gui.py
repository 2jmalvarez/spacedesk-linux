"""Small GTK 3 control panel. All network/process work runs off the UI thread."""
import copy
import threading

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from . import config as settings
from .controller import Controller
from .displays import detect


class MonitorMap(Gtk.Fixed):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.width = 0
        self.refreshing = False
        self.set_size_request(-1, 140)
        self.connect("size-allocate", self.allocated)

    def allocated(self, widget, allocation):
        if allocation.width != self.width:
            self.width = allocation.width
            self.refresh()

    def refresh(self):
        if self.refreshing:
            return
        self.refreshing = True
        for child in self.get_children():
            self.remove(child)
        displays = self.owner.displays
        if not displays:
            self.refreshing = False
            return
        min_x, min_y = min(d.x for d in displays), min(d.y for d in displays)
        span_x = max(d.x + d.width for d in displays) - min_x
        span_y = max(d.y + d.height for d in displays) - min_y
        scale = min((max(self.width, 700) - 32) / span_x, 105 / span_y)
        for number, display in enumerate(displays, 1):
            x, y = 16 + (display.x - min_x) * scale, 10 + (display.y - min_y) * scale
            width, height = display.width * scale - 4, display.height * scale - 4
            enabled = self.owner.rows.get(display.connector, {}).get("check")
            selected = enabled is not None and enabled.get_active()
            button = Gtk.Button(label=f"{number}. {display.connector}\n"
                                      f"{display.width} × {display.height}\n"
                                      f"{'Windows' if selected else 'Linux'}")
            button.set_size_request(max(100, int(width)), max(65, int(height)))
            if selected:
                button.get_style_context().add_class("suggested-action")
            button.connect("clicked", self.clicked, display.connector)
            self.put(button, int(x), int(y))
        self.show_all()
        self.refreshing = False

    def clicked(self, widget, connector):
        check = self.owner.rows[connector]["check"]
        check.set_active(not check.get_active())


class ControlWindow(Gtk.ApplicationWindow):
    def __init__(self, application, config, displays):
        super().__init__(application=application, title="spacedesk Linux — no oficial")
        self.set_default_size(790, 650)
        self.displays, self.config = displays, config
        self.rows = {}
        self.busy, self.polling, self.updating, self.closed = False, False, False, False
        self.hotplug_timer = None
        self.display = Gdk.Display.get_default()
        self.monitor_handlers = [self.display.connect(name, self.monitors_changed)
                                 for name in ("monitor-added", "monitor-removed")]
        self.connect("destroy", self.destroyed)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        self.add(root)
        title = Gtk.Label(xalign=0, label="Elegí las pantallas que querés dedicar a Windows")
        title.get_style_context().add_class("title")
        root.pack_start(title, False, False, 0)

        server = Gtk.Box(spacing=8)
        server.pack_start(Gtk.Label(label="IP de Windows:"), False, False, 0)
        self.host = Gtk.Entry(text=config["host"], placeholder_text="IP o nombre del equipo")
        server.pack_start(self.host, True, True, 0)
        self.identify = Gtk.Button(label="Identificar")
        self.identify.connect("clicked", self.identify_displays)
        server.pack_start(self.identify, False, False, 0)
        self.refresh = Gtk.Button(label="Actualizar")
        self.refresh.connect("clicked", self.refresh_displays)
        server.pack_start(self.refresh, False, False, 0)
        root.pack_start(server, False, False, 0)

        self.map = MonitorMap(self)
        root.pack_start(self.map, False, False, 0)
        controls = Gtk.Box(spacing=10)
        controls.pack_start(Gtk.Label(label="Cantidad para Windows:"), False, False, 0)
        self.count = Gtk.SpinButton.new_with_range(0, len(displays), 1)
        self.count.connect("value-changed", self.change_count)
        controls.pack_start(self.count, False, False, 0)
        controls.pack_start(Gtk.Label(label="Calidad JPEG:"), False, False, 0)
        self.quality = Gtk.SpinButton.new_with_range(1, 100, 1)
        self.quality.set_value(config["quality"])
        self.quality.set_tooltip_text("Más calidad mejora nitidez pero usa más red. No cambia la resolución.")
        controls.pack_start(self.quality, False, False, 0)
        root.pack_start(controls, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        scroll.add(self.list)
        root.pack_start(scroll, True, True, 0)
        self.build_rows()

        self.message = Gtk.Label(xalign=0, wrap=True, selectable=True)
        root.pack_start(self.message, False, False, 0)
        actions = Gtk.Box(spacing=8)
        self.save_button = Gtk.Button(label="Guardar configuración")
        self.save_button.connect("clicked", self.save_settings)
        self.stop_button = Gtk.Button(label="Desconectar todo")
        self.stop_button.connect("clicked", self.disconnect_all)
        self.connect_button = Gtk.Button(label="Conectar / aplicar")
        self.connect_button.get_style_context().add_class("suggested-action")
        self.connect_button.connect("clicked", self.connect_all)
        for button in (self.save_button, self.stop_button, self.connect_button):
            actions.pack_start(button, True, True, 0)
        root.pack_start(actions, False, False, 0)
        note = Gtk.Label(xalign=0, wrap=True, label=(
            "Seleccioná destinos en Linux. El orden del escritorio extendido se ajusta en Windows.\n"
            "Cerrar este panel no cierra los visores. Usá Desconectar todo para detenerlos."))
        note.get_style_context().add_class("dim-label")
        root.pack_start(note, False, False, 0)
        selected = {s["connector"] for s in config["screens"] if s["enabled"]}
        free = next((d for d in displays if d.connector not in selected), None)
        if free:
            self.move(free.x + 20, free.y + 35)
        self.show_all()
        self.timer = GLib.timeout_add_seconds(2, self.poll_status)
        self.poll_status()

    def destroyed(self, *args):
        self.closed = True
        if getattr(self, "timer", None):
            GLib.source_remove(self.timer)
        if self.hotplug_timer is not None:
            GLib.source_remove(self.hotplug_timer)
        for handler in self.monitor_handlers:
            self.display.disconnect(handler)

    def monitors_changed(self, *args):
        if self.hotplug_timer is not None:
            GLib.source_remove(self.hotplug_timer)
        self.hotplug_timer = GLib.timeout_add(600, self.refresh_after_hotplug)

    def refresh_after_hotplug(self):
        if self.closed:
            return False
        if self.busy:
            return True
        self.hotplug_timer = None
        # Refresh destinations only: never auto-connect or silently reassign one.
        self.refresh_displays()
        return False

    def build_rows(self):
        self.updating = True
        for child in self.list.get_children():
            self.list.remove(child)
        self.rows = {}
        available = {d.connector: d for d in self.displays}
        for screen in self.config["screens"]:
            display = available.get(screen["connector"])
            row = Gtk.Box(spacing=10)
            check = Gtk.CheckButton(label=screen["connector"] + (" (no disponible)" if display is None else ""))
            check.set_active(screen["enabled"])
            check.connect("toggled", self.selection_changed)
            row.pack_start(check, False, False, 0)
            combo = Gtk.ComboBoxText()
            native = display.native if display else (screen["width"] or 0, screen["height"] or 0)
            combo.append("native", f"Nativa ({native[0]} × {native[1]})")
            modes = list(display.modes) if display else []
            configured = (screen["width"], screen["height"])
            if configured[0] is not None and configured not in modes:
                modes.append(configured)
            for width, height in modes:
                combo.append(f"{width}x{height}", f"{width} × {height}")
            combo.set_active_id("native" if configured[0] is None else f"{configured[0]}x{configured[1]}")
            row.pack_start(combo, False, False, 0)
            label = Gtk.Label(xalign=0, wrap=True, label="Sin conexión")
            row.pack_start(label, True, True, 0)
            self.list.pack_start(row, False, False, 0)
            self.rows[screen["connector"]] = {"check": check, "resolution": combo,
                                                "status": label, "screen": screen}
        self.count.set_range(0, max(len(self.displays), sum(s["enabled"] for s in self.config["screens"])))
        self.updating = False
        self.selection_changed()
        self.list.show_all()

    def selection_changed(self, *args):
        if self.updating:
            return
        self.updating = True
        self.count.set_value(sum(row["check"].get_active() for row in self.rows.values()))
        self.updating = False
        self.map.refresh()

    def change_count(self, *args):
        if self.updating:
            return
        wanted = self.count.get_value_as_int()
        available = {d.connector for d in self.displays}
        selected = [r for key, r in self.rows.items() if r["check"].get_active() and key in available]
        remaining = sorted((d for d in self.displays if not self.rows[d.connector]["check"].get_active()),
                           key=lambda d: (-d.native[0] * d.native[1], d.x))
        target = {id(row) for row in selected[:wanted]}
        target.update(id(self.rows[d.connector]) for d in remaining[:max(0, wanted - len(selected))])
        self.updating = True
        for row in self.rows.values():
            row["check"].set_active(id(row) in target)
        self.updating = False
        self.selection_changed()

    def read_settings(self):
        value = copy.deepcopy(self.config)
        value.update(host=self.host.get_text().strip(), quality=self.quality.get_value_as_int())
        for screen in value["screens"]:
            row = self.rows[screen["connector"]]
            screen["enabled"] = row["check"].get_active()
            resolution = row["resolution"].get_active_id()
            screen["width"], screen["height"] = (None, None) if resolution == "native" else map(int, resolution.split("x"))
        return settings.validate(value)

    def save_settings(self, *args):
        try:
            self.config = self.read_settings()
            settings.save(self.config)
            self.message.set_text("Guardado. Conectar / aplicar activa los cambios.")
        except Exception as error:
            self.message.set_text(str(error))

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.host, self.count, self.quality, self.list, self.map, self.save_button,
                       self.connect_button, self.stop_button, self.refresh, self.identify):
            widget.set_sensitive(not busy)

    def work(self, action, success):
        if self.busy:
            self.message.set_text("Esperá a que termine la operación actual.")
            return
        self.set_busy(True)

        def worker():
            try:
                result, error = action(), None
            except Exception as exception:
                result, error = None, str(exception)

            def complete():
                if self.closed:
                    return False
                self.set_busy(False)
                if error:
                    self.message.set_text(error)
                else:
                    success(result)
                return False
            GLib.idle_add(complete)
        threading.Thread(target=worker, daemon=True).start()

    def connect_all(self, *args):
        try:
            config = self.read_settings()
            settings.validate(config, self.displays, connecting=True)
            settings.save(config)
            self.config = config
        except Exception as error:
            self.message.set_text(str(error))
            return
        self.message.set_text("Conectando las pantallas seleccionadas...")
        self.work(lambda: Controller(config).connect(), self.connected)

    def connected(self, statuses):
        self.show_statuses(statuses)
        self.message.set_text("Configuración aplicada. Las pantallas seleccionadas reciben Windows.")

    def disconnect_all(self, *args):
        config = copy.deepcopy(self.config)
        self.work(lambda: Controller(config).stop(),
                  lambda _: self.message.set_text("Todos los visores fueron detenidos."))

    def show_statuses(self, statuses):
        for row in self.rows.values():
            state = statuses.get(row["screen"]["id"], {})
            message = state.get("message", "Detenido")
            if state.get("state") == "streaming":
                message = f"Conectado · {state['width']} × {state['height']}"
            row["status"].set_text(message)

    def poll_status(self):
        if self.closed:
            return False
        if self.busy or self.polling:
            return True
        self.polling = True
        config = copy.deepcopy(self.config)

        def worker():
            try:
                statuses = Controller(config).statuses()
            except Exception:
                statuses = {}

            def complete():
                self.polling = False
                if not self.closed:
                    self.show_statuses(statuses)
                return False
            GLib.idle_add(complete)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def refresh_displays(self, *args):
        try:
            current = self.read_settings()
        except Exception as error:
            self.message.set_text(str(error))
            return

        def updated(displays):
            self.displays = displays
            self.config = settings.reconcile(current, displays)
            self.build_rows()
            self.map.refresh()
            self.message.set_text("Monitores actualizados. No se reemplazaron destinos guardados.")
        self.work(detect, updated)

    def identify_displays(self, *args):
        for number, display in enumerate(self.displays, 1):
            overlay = Gtk.Window(type=Gtk.WindowType.POPUP)
            overlay.add(Gtk.Label(label=f"\n   {number}: {display.connector}   \n"
                                      f"   {display.width} × {display.height}   \n"))
            overlay.move(display.x + 40, display.y + 60)
            overlay.show_all()
            GLib.timeout_add(2500, lambda window=overlay: (window.destroy(), False)[1])


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.unofficial.SpacedeskLinux")
        self.window = None

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return
        try:
            displays = detect()
            config = settings.load()
            config = settings.default_config(displays) if config is None else settings.reconcile(config, displays)
            self.window = ControlWindow(self, config, displays)
        except Exception as error:
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                       buttons=Gtk.ButtonsType.CLOSE, text=str(error))
            dialog.run()
            dialog.destroy()


def main():
    # argparse already consumed our subcommand; GTK must not treat "gui" as a file.
    return Application().run(["spacedesk-linux"])
