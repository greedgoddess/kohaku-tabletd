"""The single control instance: watches the hinge, owns the D-Bus API, applies scales."""

import logging
import shlex
import signal
import subprocess

from gi.repository import Gio, GLib

from . import BUS_NAME, INTERFACE, OBJECT_PATH, config, mutter, state, switch

log = logging.getLogger("kohaku-tabletd")

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
    <signal name="ModeChanged">
      <arg type="s" name="mode"/>
      <arg type="d" name="scale"/>
      <arg type="b" name="manual"/>
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
        self.bus.emit_signal(None, OBJECT_PATH, INTERFACE, "ModeChanged",
                             GLib.Variant("(sdb)", (mode, scale, self.state.manual)))
        return mode

    def _apply_logged(self):
        try:
            self.apply()
        except ApplyError as exc:
            log.error("apply failed: %s", exc)

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
        if self.state.hinge(state.TABLET if tablet else state.LAPTOP):
            self._apply_logged()
        return GLib.SOURCE_REMOVE

    # [doc:dmn-dbus-methods]
    def _on_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "Status":
            invocation.return_value(GLib.Variant("(a{sv})", (self.status(),)))
            return
        try:
            if method == "Toggle":
                self.state.toggle()
            elif method == "SetMode":
                self.state.set(params.unpack()[0])
            elif method == "Auto":
                self.state.auto()
            elif method != "Reapply":
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
                return
            invocation.return_value(GLib.Variant("(s)", (self.apply(),)))
        except ValueError as exc:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.InvalidArgs", str(exc))
        except ApplyError as exc:
            invocation.return_dbus_error(f"{INTERFACE}.Error.ApplyFailed", str(exc))

    def status(self):
        return {
            "mode": GLib.Variant("s", self.state.effective),
            "physical": GLib.Variant("s", self.state.physical),
            "manual": GLib.Variant("b", self.state.manual),
            "scale": GLib.Variant("d", self.scale),
            "switch": GLib.Variant("s", self.switch.path_in_use or ""),
        }

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
