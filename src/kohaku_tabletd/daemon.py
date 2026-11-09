"""The single control instance: watches the hinge, owns the D-Bus API, applies scales."""

import collections
import logging
import shlex
import signal
import subprocess
import time

from gi.repository import Gio, GLib

from . import BUS_NAME, HINGE_SOURCE, INTERFACE, OBJECT_PATH, callers, config, mutter, state, switch

log = logging.getLogger("kohaku-tabletd")
TRIGGERS = ("Toggle", "SetMode", "Auto", "Reapply")
RECENT_MAX = 50

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

    # [doc:dmn-apply]
    def apply(self):
        """Apply the scale for the effective mode. Raises ApplyError."""
        mode = self.state.effective
        target = self.cfg.tablet_scale if mode == state.TABLET else self.cfg.laptop_scale
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
        return GLib.SOURCE_REMOVE

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
            "laptop_scale": GLib.Variant("d", self.cfg.laptop_scale),
            "tablet_scale": GLib.Variant("d", self.cfg.tablet_scale),
            "blocklist": GLib.Variant("as", list(self.cfg.blocklist)),
            "supported_scales": GLib.Variant("ad", supported),
        }

    def set_settings(self, changes):
        """Validate, persist to the user config, adopt, reapply if a scale changed."""
        update = config.validate_update(changes)
        config.save_user(update)
        scales_before = (self.cfg.laptop_scale, self.cfg.tablet_scale)
        for key, value in update.items():
            setattr(self.cfg, key, value)
        self._emit("SettingsChanged", GLib.Variant("(a{sv})", (self.settings(),)))
        if (self.cfg.laptop_scale, self.cfg.tablet_scale) != scales_before:
            self._apply_logged()

    # [doc:dmn-run]
    def run(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
        self.bus.register_object(OBJECT_PATH, node.interfaces[0], self._on_call, None, None)
        Gio.bus_own_name_on_connection(self.bus, BUS_NAME, Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                                       self._on_acquired, self._on_lost)
        for signum in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._quit)
        self.loop.run()
        return self.exit_code

    def _on_acquired(self, _conn, _name):
        self.attach_switch()
        self._apply_logged()

    def _on_lost(self, _conn, name):
        log.error("could not own %s; is another instance running?", name)
        self.exit_code = 1
        self.loop.quit()

    def _quit(self):
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
