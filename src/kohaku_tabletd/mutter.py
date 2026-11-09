"""Apply a display scale through Mutter's DisplayConfig D-Bus API (GNOME)."""

from gi.repository import Gio, GLib

from . import layout

BUS = "org.gnome.Mutter.DisplayConfig"
PATH = "/org/gnome/Mutter/DisplayConfig"
IFACE = BUS
METHOD_TEMPORARY = 1  # persistent (2) makes GNOME ask "keep changes?"
LAYOUT_LOGICAL = 1
STATE_TYPE = "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"
APPLY_TYPE = "(uua(iiduba(ssa{sv}))a{sv})"


class MutterError(RuntimeError):
    pass


# [doc:mut-state]
def read_state(bus):
    """(serial, logical monitors as dicts, current mode id per connector, properties)."""
    reply = bus.call_sync(BUS, PATH, IFACE, "GetCurrentState", None,
                          GLib.VariantType(STATE_TYPE), Gio.DBusCallFlags.NONE, -1, None)
    serial, monitors, logical, props = reply.unpack()
    current = {}
    for (connector, _vendor, _product, _serial), modes, mprops in monitors:
        for mode_id, width, height, _rate, _pref, supported, mode_props in modes:
            if mode_props.get("is-current"):
                current[connector] = {
                    "mode": mode_id, "width": width, "height": height,
                    "supported": list(supported), "builtin": bool(mprops.get("is-builtin")),
                }
    lms = []
    for x, y, scale, transform, primary, mons, _lprops in logical:
        conns = [m[0] for m in mons if m[0] in current]
        if not conns:
            continue
        first = current[conns[0]]
        lms.append({
            "x": x, "y": y, "scale": scale, "transform": transform, "primary": primary,
            "connectors": conns, "width": first["width"], "height": first["height"],
            "supported": first["supported"],
            "builtin": any(current[c]["builtin"] for c in conns),
        })
    return serial, lms, {c: v["mode"] for c, v in current.items()}, props


# [doc:mut-apply]
def apply_scale(target, output=""):
    """Rescale one monitor (nearest supported scale), keep everything else.
    Applied as a temporary config: no confirmation dialog, and the daemon
    reapplies the right scale at login anyway. Returns the scale used."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    serial, lms, modes, props = read_state(bus)
    index = layout.find_target(lms, output)
    if index is None:
        raise MutterError(f"no active monitor for {output or 'the built-in panel'}")
    scale = layout.pick_scale(target, lms[index]["supported"])
    if abs(scale - lms[index]["scale"]) < 1e-4:
        return scale
    logical_layout = props.get("layout-mode", LAYOUT_LOGICAL) == LAYOUT_LOGICAL
    new = layout.rescale(lms, index, scale, logical_layout)
    config = [
        (lm["x"], lm["y"], lm["scale"], lm["transform"], lm["primary"],
         [(c, modes[c], {}) for c in lm["connectors"]])
        for lm in new
    ]
    apply_props = {}
    if props.get("supports-changing-layout-mode") and "layout-mode" in props:
        apply_props["layout-mode"] = GLib.Variant("u", props["layout-mode"])
    bus.call_sync(BUS, PATH, IFACE, "ApplyMonitorsConfig",
                  GLib.Variant(APPLY_TYPE, (serial, METHOD_TEMPORARY, config, apply_props)),
                  None, Gio.DBusCallFlags.NONE, -1, None)
    return scale
