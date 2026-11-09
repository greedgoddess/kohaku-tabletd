"""Command line: `kohaku-tabletd daemon` runs the service, every other command talks to it."""

import argparse
import os
import pwd
import sys

from . import BUS_NAME, INTERFACE, OBJECT_PATH, __version__

# [doc:cli-commands]
COMMANDS = {
    "toggle": ("Toggle", None, "switch to the other mode (manual override)"),
    "laptop": ("SetMode", "laptop", "force laptop scaling (manual override)"),
    "tablet": ("SetMode", "tablet", "force tablet scaling (manual override)"),
    "auto": ("Auto", None, "drop the override and follow the hinge again"),
    "reapply": ("Reapply", None, "apply the current mode's scale again"),
    "status": ("Status", None, "show mode, override and scale"),
}


# [doc:cli-active-user]
def become_active_user():
    """Running as root (keyd's command()): switch to the owner of the active
    seat0 session so the call lands on their session bus."""
    if os.geteuid() != 0:
        return
    from gi.repository import Gio, GLib

    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def prop(path, iface, name):
        reply = system.call_sync("org.freedesktop.login1", path,
                                 "org.freedesktop.DBus.Properties", "Get",
                                 GLib.Variant("(ss)", (iface, name)), GLib.VariantType("(v)"),
                                 Gio.DBusCallFlags.NONE, -1, None)
        return reply.unpack()[0]

    session_id, session_path = prop("/org/freedesktop/login1/seat/seat0",
                                    "org.freedesktop.login1.Seat", "ActiveSession")
    if not session_id:
        raise SystemExit("kohaku-tabletd: no active session on seat0")
    uid, _user_path = prop(session_path, "org.freedesktop.login1.Session", "User")
    user = pwd.getpwuid(uid)
    os.initgroups(user.pw_name, user.pw_gid)
    os.setgid(user.pw_gid)
    os.setuid(uid)
    os.environ.update({
        "HOME": user.pw_dir,
        "USER": user.pw_name,
        "XDG_RUNTIME_DIR": f"/run/user/{uid}",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus",
    })


# [doc:cli-call]
def call(command):
    from gi.repository import Gio, GLib

    method, arg, _help = COMMANDS[command]
    params = GLib.Variant("(s)", (arg,)) if arg else None
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(BUS_NAME, OBJECT_PATH, INTERFACE, method, params, None,
                              Gio.DBusCallFlags.NONE, 20000, None)
    except GLib.Error as exc:
        Gio.DBusError.strip_remote_error(exc)
        print(f"kohaku-tabletd: {exc.message}", file=sys.stderr)
        return 1
    result = reply.unpack()[0]
    if isinstance(result, dict):
        for key in sorted(result):
            print(f"{key}={result[key]}")
    else:
        print(result)
    return 0


# [doc:cli-main]
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="kohaku-tabletd",
        description="Tablet-mode aware display scaling with a single control daemon.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--active-user", action="store_true",
                        help="when run as root (e.g. from keyd), act in the active session on seat0")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    sub.add_parser("daemon", help="run the control daemon (started by systemd --user)")
    for name, (_method, _arg, text) in COMMANDS.items():
        sub.add_parser(name, help=text)
    args = parser.parse_args(argv)
    if args.command == "daemon":
        from .daemon import main as run_daemon
        return run_daemon()
    if args.active_user:
        become_active_user()
    return call(args.command)
