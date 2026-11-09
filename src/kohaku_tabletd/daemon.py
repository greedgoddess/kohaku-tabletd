"""The single control instance: watches the hinge, owns the D-Bus API, applies scales."""

import collections
import logging
import shlex
import signal
import subprocess
import threading
import time

from gi.repository import Gio, GLib

from . import (BUS_NAME, HINGE_SOURCE, INTERFACE, OBJECT_PATH, SETTINGS_APP_ID, __version__,
               callers, config, integration, monitorsxml, mutter, sensors, state, switch, updates)

log = logging.getLogger("kohaku-tabletd")
TRIGGERS = ("Toggle", "SetMode", "Auto", "Reapply")
RECENT_MAX = 50
UPDATE_INTERVAL_MS = 23 * 3600 * 1000  # "daily", with slack for the hourly timer
USER_MONITORS_XML = monitorsxml.config_paths()[0]
NOTIFY = ("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
          "org.freedesktop.Notifications")

# [doc:dmn-iface]
INTROSPECTION = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="Toggle"><arg direction="out" type="s" name="mode"/></method>
    <method name="SetMode">
      <arg direction="in" type="s" name="requested"/>
      <arg direction="out" type="s" name="mode"/>
    </method>
    <method name="Auto"><arg direction="out" type="s" name="mode"/></method>
    <method name="Reapply"><arg direction="out" type="s" name="mode"/></method>
    <method name="Status"><arg direction="out" type="a{{sv}}" name="status"/></method>
    <method name="GetSettings"><arg direction="out" type="a{{sv}}" name="settings"/></method>
    <method name="SetSettings"><arg direction="in" type="a{{sv}}" name="changes"/></method>
    <method name="RecentCalls"><arg direction="out" type="a(xsssb)" name="calls"/></method>
    <method name="CheckForUpdates"/>
    <signal name="ModeChanged">
      <arg type="s" name="mode"/>
      <arg type="d" name="scale"/>
      <arg type="b" name="manual"/>
    </signal>
    <signal name="SettingsChanged"><arg type="a{{sv}}" name="settings"/></signal>
    <signal name="CallRecorded">
      <arg type="x" name="time_ms"/>
      <arg type="s" name="action"/>
      <arg type="s" name="source"/>
      <arg type="s" name="chain"/>
      <arg type="b" name="blocked"/>
    </signal>
  </interface>
</node>
"""


class ApplyError(RuntimeError):
    pass


class Daemon:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = state.ModeState()
        self.switch = switch.TabletSwitch(cfg.switch_device)
        self.loop = GLib.MainLoop()
        self.bus = None
        self.scale = 0.0
        self.exit_code = 0
        self.recent = collections.deque(maxlen=RECENT_MAX)
        self._debounce_id = 0
        self._missing_logged = False
        self.update = {"state": "never", "latest": "", "url": updates.RELEASES_URL,
                       "checked": 0, "error": "", "notified": ""}
        self.update.update(updates.load_state())
        self._update_running = False
        self._notify_urls = {}  # notification id -> page its click opens
        self.freeze = sensors.FreezeDetector()
        self.accelerometers = sensors.accelerometers()
        self.sensor_warning = ""
        self._display_timer = 0
        self._saved_config_changed = False
        self._xml_monitor = None
        self._default_pending = None  # (scale, monotonic time) while GNOME's dialog is open
        self.integrations = integration.IntegrationManager(cfg.integrations)

    # [doc:dmn-apply]
    def apply(self):
        """Apply the scale for the effective mode. Raises ApplyError."""
        mode = self.state.effective
        target = self.cfg.tablet_scale if mode == state.TABLET else self.default_scale()
        try:
            if self.cfg.apply_command:
                argv = [arg.replace("{scale}", f"{target:g}").replace("{mode}", mode)
                        for arg in shlex.split(self.cfg.apply_command)]
                subprocess.run(argv, check=True, timeout=15)
                scale = target
            else:
                scale = mutter.apply_scale(target, self.cfg.output)
        except (OSError, subprocess.SubprocessError, GLib.Error, mutter.MutterError) as exc:
            raise ApplyError(f"{mode} ({target:g}): {exc}") from exc
        if abs(scale - target) > 0.01:
            log.warning("scale %g not offered by Mutter, used nearest %g", target, scale)
        self.scale = scale
        log.info("mode=%s scale=%g manual=%s", mode, scale, self.state.manual)
        self._emit("ModeChanged", GLib.Variant("(sdb)", (mode, scale, self.state.manual)))
        return mode

    # [doc:dmn-default]
    def default_scale(self):
        """GNOME's saved scale for the panel; laptop_scale only as a fallback."""
        if not self.cfg.apply_command:
            try:
                saved = mutter.default_scale(self.cfg.output)
            except (GLib.Error, mutter.MutterError) as exc:
                log.warning("cannot read GNOME's saved scale: %s", exc)
                saved = None
            if saved is not None:
                return saved
        return self.cfg.laptop_scale

    def set_default_scale(self, scale):
        """Change GNOME's saved scale. GNOME shows its keep-changes dialog and
        only saves on confirm; the monitors.xml watch picks the result up."""
        if self.cfg.apply_command:
            config.save_user({"laptop_scale": scale})
            self.cfg.laptop_scale = scale
            if self.state.effective == state.LAPTOP:
                self._apply_logged()
            return
        try:
            self.scale = mutter.apply_scale(scale, self.cfg.output, persistent=True)
        except (GLib.Error, mutter.MutterError) as exc:
            raise ApplyError(f"default scale {scale:g}: {exc}") from exc
        self._default_pending = (scale, time.monotonic())
        log.info("default scale %g requested, waiting for GNOME's confirmation", scale)

    # [doc:dmn-display-watch]
    def _on_display_event(self, saved_config_changed):
        """Mutter's MonitorsChanged or a write to monitors.xml (debounced)."""
        self._saved_config_changed |= saved_config_changed
        pending = self._default_pending
        # Confirmed (monitors.xml written) or reverted (a later MonitorsChanged):
        # either way GNOME's saved value is the truth again.
        if pending and (saved_config_changed or time.monotonic() - pending[1] > 2):
            self._default_pending = None
        if self._display_timer:
            GLib.source_remove(self._display_timer)
        self._display_timer = GLib.timeout_add(500, self._display_settled)

    def _display_settled(self):
        """Refresh listeners. If GNOME saved a new config while in tablet mode
        (default confirmed), put the temporary zoom back."""
        self._display_timer = 0
        reapply = self._saved_config_changed and self.state.effective == state.TABLET
        self._saved_config_changed = False
        self._emit_settings()
        if reapply:
            self._apply_logged()
        return GLib.SOURCE_REMOVE

    def _watch_display(self):
        self.bus.signal_subscribe(None, mutter.IFACE, "MonitorsChanged", mutter.PATH, None,
                                  Gio.DBusSignalFlags.NONE,
                                  lambda *_args: self._on_display_event(False))
        self._xml_monitor = Gio.File.new_for_path(USER_MONITORS_XML).monitor_file(
            Gio.FileMonitorFlags.NONE, None)
        self._xml_monitor.connect("changed", lambda *_args: self._on_display_event(True))

    def _apply_logged(self):
        try:
            self.apply()
        except ApplyError as exc:
            log.error("apply failed: %s", exc)

    def _emit(self, name, params):
        self.bus.emit_signal(None, OBJECT_PATH, INTERFACE, name, params)

    # [doc:dmn-record]
    def record(self, action, source, chain, blocked):
        """Remember a trigger (newest last) and tell listeners like the settings window."""
        entry = (int(time.time() * 1000), action, source, chain, blocked)
        self.recent.append(entry)
        log.info("%s from %s (%s)%s", action, source, chain, " BLOCKED" if blocked else "")
        self._emit("CallRecorded", GLib.Variant("(xsssb)", entry))

    # [doc:dmn-identify]
    def identify(self, sender):
        """Map a D-Bus sender to (source, chain) via its PID and /proc."""
        try:
            reply = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                       "org.freedesktop.DBus", "GetConnectionUnixProcessID",
                                       GLib.Variant("(s)", (sender,)), GLib.VariantType("(u)"),
                                       Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error:
            return "unknown", sender
        return callers.identify(reply.unpack()[0])

    # [doc:dmn-switch-attach]
    def attach_switch(self):
        """Open the tablet-mode switch and record its state; retry later if
        it is missing. Returns True if the physical mode changed."""
        try:
            opened = self.switch.open()
            tablet = self.switch.tablet() if opened else False
        except OSError as exc:
            log.warning("cannot use tablet switch: %s", exc)
            self.switch.close()
            opened = False
        if not opened:
            if not self._missing_logged:
                log.info("no tablet-mode switch yet; retrying every 10 s, manual control works")
                self._missing_logged = True
            GLib.timeout_add_seconds(10, self._retry_switch)
            return False
        self._missing_logged = False
        log.info("watching %s", self.switch.path_in_use)
        GLib.io_add_watch(self.switch.fd, GLib.PRIORITY_DEFAULT,
                          GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR,
                          self._on_switch)
        return self.state.hinge(state.TABLET if tablet else state.LAPTOP)

    def _retry_switch(self):
        if self.attach_switch():
            self._apply_logged()
            self.sync_integrations()
        return GLib.SOURCE_REMOVE

    # [doc:dmn-integrations]
    def sync_integrations(self):
        """Integrations follow the hinge (folded = tablet), not the zoom toggle."""
        if self.integrations.sync(self.state.physical == state.TABLET):
            self._emit_settings()

    # [doc:dmn-switch-event]
    def _on_switch(self, _fd, condition):
        try:
            if condition & (GLib.IOCondition.HUP | GLib.IOCondition.ERR):
                raise OSError("hangup")
            moved = self.switch.drain()
        except OSError as exc:
            log.warning("tablet switch lost (%s), reattaching", exc)
            self.switch.close()
            GLib.timeout_add_seconds(2, self._retry_switch)
            return GLib.SOURCE_REMOVE
        if moved:
            if self._debounce_id:
                GLib.source_remove(self._debounce_id)
            self._debounce_id = GLib.timeout_add(self.cfg.debounce_ms, self._settled)
        return GLib.SOURCE_CONTINUE

    # [doc:dmn-debounce]
    def _settled(self):
        """Hinge has been quiet for debounce_ms: read the real state once."""
        self._debounce_id = 0
        try:
            tablet = self.switch.tablet()
        except (OSError, TypeError):
            return GLib.SOURCE_REMOVE
        physical = state.TABLET if tablet else state.LAPTOP
        if self.state.hinge(physical):
            self.record(f"Hinge({physical})", HINGE_SOURCE, "tablet-mode switch", False)
            self._apply_logged()
            self.sync_integrations()
        return GLib.SOURCE_REMOVE

    # [doc:dmn-dbus-methods]
    def _on_call(self, _conn, sender, _path, _iface, method, params, invocation):
        try:
            if method in TRIGGERS:
                self._trigger(sender, method, params, invocation)
            elif method == "Status":
                invocation.return_value(GLib.Variant("(a{sv})", (self.status(),)))
            elif method == "GetSettings":
                invocation.return_value(GLib.Variant("(a{sv})", (self.settings(),)))
            elif method == "SetSettings":
                self.set_settings(params.unpack()[0])
                invocation.return_value(None)
            elif method == "CheckForUpdates":
                self.check_updates()
                invocation.return_value(None)
            elif method == "RecentCalls":
                invocation.return_value(GLib.Variant("(a(xsssb))", (list(self.recent),)))
            else:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
        except (ValueError, TypeError) as exc:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(exc))
        except OSError as exc:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(exc))
        except ApplyError as exc:
            invocation.return_dbus_error(f"{INTERFACE}.Error.ApplyFailed", str(exc))

    # [doc:dmn-trigger]
    def _trigger(self, sender, method, params, invocation):
        """Trigger API: identify and record the caller, refuse blocked sources, act."""
        source, chain = self.identify(sender)
        action = f"SetMode({params.unpack()[0]})" if method == "SetMode" else method
        blocked = source in self.cfg.blocklist
        self.record(action, source, chain, blocked)
        if blocked:
            invocation.return_dbus_error(f"{INTERFACE}.Error.Blocked",
                                         f"{source} is blocked in kohaku-tabletd settings")
            return
        if method == "Toggle":
            self.state.toggle()
        elif method == "SetMode":
            self.state.set(params.unpack()[0])
        elif method == "Auto":
            self.state.auto()
        invocation.return_value(GLib.Variant("(s)", (self.apply(),)))

    def status(self):
        return {
            "mode": GLib.Variant("s", self.state.effective),
            "physical": GLib.Variant("s", self.state.physical),
            "manual": GLib.Variant("b", self.state.manual),
            "scale": GLib.Variant("d", self.scale),
            "switch": GLib.Variant("s", self.switch.path_in_use or ""),
        }

    # [doc:dmn-settings]
    def settings(self):
        supported = []
        if not self.cfg.apply_command:
            try:
                supported = mutter.supported_scales(self.cfg.output)
            except (GLib.Error, mutter.MutterError) as exc:
                log.warning("cannot read supported scales: %s", exc)
        return {
            "default_scale": GLib.Variant("d", self._default_pending[0] if self._default_pending
                                          else self.default_scale()),
            "default_pending": GLib.Variant("b", self._default_pending is not None),
            "tablet_scale": GLib.Variant("d", self.cfg.tablet_scale),
            "blocklist": GLib.Variant("as", list(self.cfg.blocklist)),
            "supported_scales": GLib.Variant("ad", supported),
            "update_check": GLib.Variant("b", self.cfg.update_check),
            "sensor_warning": GLib.Variant("s", self.sensor_warning),
            "integrations": GLib.Variant("aa{sv}", [
                {"id": GLib.Variant("s", row["id"]), "title": GLib.Variant("s", row["title"]),
                 "description": GLib.Variant("s", row["description"]),
                 "category": GLib.Variant("s", row["category"]),
                 "enabled": GLib.Variant("b", row["enabled"]),
                 "available": GLib.Variant("b", row["available"]),
                 "active": GLib.Variant("b", row["active"]), "note": GLib.Variant("s", row["note"])}
                for row in self.integrations.describe()]),
            "update_state": GLib.Variant("s", self.update["state"]),
            "update_latest": GLib.Variant("s", self.update["latest"]),
            "update_url": GLib.Variant("s", self.update["url"]),
            "update_checked": GLib.Variant("x", self.update["checked"]),
            "update_error": GLib.Variant("s", self.update["error"]),
        }

    def _emit_settings(self):
        self._emit("SettingsChanged", GLib.Variant("(a{sv})", (self.settings(),)))

    def set_settings(self, changes):
        """Validate; the default scale goes to GNOME, everything else to the
        user config. Reapplies if the temporary zoom changed while active."""
        update = config.validate_update(changes)
        default = update.pop("default_scale", None)
        if update:
            config.save_user(update)
        tablet_before = self.cfg.tablet_scale
        for key, value in update.items():
            setattr(self.cfg, key, value)
        if default is not None:
            self.set_default_scale(default)
        if "integrations" in update:
            self.integrations.enabled = set(update["integrations"])
            self.integrations.sync(self.state.physical == state.TABLET)
        self._emit_settings()
        if self.cfg.tablet_scale != tablet_before and self.state.effective == state.TABLET:
            self._apply_logged()
        if update.get("update_check"):
            self._periodic_update()

    # [doc:dmn-updates]
    def check_updates(self):
        """Check GitHub releases in a worker thread; the result lands in _update_done."""
        if self._update_running:
            return
        self._update_running = True
        self.update["state"] = "checking"
        self._emit_settings()
        threading.Thread(target=lambda: GLib.idle_add(self._update_done, updates.check()),
                         daemon=True).start()

    def _update_done(self, result):
        self._update_running = False
        self.update.update(result)
        log.info("update check: %s %s", result["state"], result["latest"] or result["error"])
        if result["state"] == "available" and result["latest"] != self.update["notified"]:
            self.notify(f"kohaku-tabletd {result['latest']} is available",
                        f"You have {__version__}. Open the release page to get the new RPM.",
                        "Open release page", result["url"])
            self.update["notified"] = result["latest"]
        try:
            updates.save_state(self.update)
        except OSError as exc:
            log.warning("cannot save update state: %s", exc)
        self._emit_settings()
        return GLib.SOURCE_REMOVE

    def _periodic_update(self):
        """Hourly tick: check if enabled and the last check is about a day old."""
        if self.cfg.update_check and time.time() * 1000 - self.update["checked"] > UPDATE_INTERVAL_MS:
            self.check_updates()
        return GLib.SOURCE_CONTINUE

    def _first_update_check(self):
        self._periodic_update()
        return GLib.SOURCE_REMOVE

    # [doc:dmn-sensor-check]
    def _check_sensors(self):
        """Every 2 s: read the EC accelerometers; warn once when one is frozen."""
        readings = {label: sensors.read_accel(path) for label, path in self.accelerometers.items()}
        frozen = self.freeze.update(time.monotonic(), readings)
        warning = ""
        if frozen:
            warning = (f"Hinge sensor {', '.join(sorted(frozen))} stopped updating, so tablet mode "
                       "is detected wrongly. Shut down, then hold Refresh and press Power.")
        if warning == self.sensor_warning:
            return GLib.SOURCE_CONTINUE
        if warning and not self.sensor_warning:
            log.warning("frozen accelerometer: %s", ", ".join(sorted(frozen)))
            self.notify("Tablet mode detection unreliable", warning,
                        "How to fix", updates.TROUBLESHOOTING_DOC_URL)
        elif not warning:
            log.info("accelerometers update again")
        self.sensor_warning = warning
        self._emit_settings()
        return GLib.SOURCE_CONTINUE

    # [doc:dmn-notify]
    def notify(self, summary, body, button, url):
        """Desktop notification under the app's name; clicking it opens url."""
        params = GLib.Variant("(susssasa{sv}i)", (
            "Tablet Mode", 0, SETTINGS_APP_ID, summary, body,
            ["default", button, "open", button],
            {"desktop-entry": GLib.Variant("s", SETTINGS_APP_ID)}, -1))
        self.bus.call(*NOTIFY, "Notify", params, GLib.VariantType("(u)"),
                      Gio.DBusCallFlags.NONE, -1, None, self._on_notified, url)

    def _on_notified(self, bus, result, url):
        try:
            self._notify_urls[bus.call_finish(result).unpack()[0]] = url
        except GLib.Error as exc:
            log.warning("notification failed: %s", exc.message)

    def _on_notify_action(self, _conn, _sender, _path, _iface, _signal, params):
        notification_id, action = params.unpack()
        url = self._notify_urls.get(notification_id)
        if url and action in ("default", "open"):
            try:
                Gio.AppInfo.launch_default_for_uri(url, None)
            except GLib.Error as exc:
                log.warning("cannot open %s: %s", url, exc.message)

    # [doc:dmn-run]
    def run(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
        self.bus.register_object(OBJECT_PATH, node.interfaces[0], self._on_call, None, None)
        Gio.bus_own_name_on_connection(self.bus, BUS_NAME, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                                       self._on_acquired, self._on_lost)
        self._watch_display()
        self.bus.signal_subscribe(None, NOTIFY[2], "ActionInvoked", NOTIFY[1], None,
                                  Gio.DBusSignalFlags.NONE, self._on_notify_action)
        GLib.timeout_add_seconds(60, self._first_update_check)
        GLib.timeout_add_seconds(3600, self._periodic_update)
        if len(self.accelerometers) >= 2:
            GLib.timeout_add_seconds(2, self._check_sensors)
        for signum in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._quit)
        self.loop.run()
        return self.exit_code

    def _on_acquired(self, _conn, _name):
        self.attach_switch()
        self._apply_logged()
        self.sync_integrations()

    def _on_lost(self, _conn, name):
        log.error("could not own %s; is another instance running?", name)
        self.exit_code = 1
        self.loop.quit()

    def _quit(self):
        self.integrations.sync(False)  # logout/stop: give the desktop its settings back
        self.loop.quit()
        return GLib.SOURCE_REMOVE


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        cfg = config.load()
    except (ValueError, OSError) as exc:
        log.error("config: %s", exc)
        return 1
    return Daemon(cfg).run()
