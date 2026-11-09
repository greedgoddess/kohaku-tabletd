"""Display scale through Mutter's DisplayConfig D-Bus API (GNOME).

Temporary configs are used for switching (no confirmation); the default scale
is GNOME's own saved configuration, changed with a persistent config so GNOME
asks to keep it."""

from gi.repository import Gio, GLib

from . import layout, monitorsxml

BUS = "org.gnome.Mutter.DisplayConfig"
PATH = "/org/gnome/Mutter/DisplayConfig"
IFACE = BUS
METHOD_TEMPORARY = 1   # no dialog, not saved
METHOD_PERSISTENT = 2  # GNOME asks "keep changes?", saved to monitors.xml on confirm
LAYOUT_LOGICAL = 1
STATE_TYPE = "(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"
APPLY_TYPE = "(uua(iiduba(ssa{sv}))a{sv})"


class MutterError(RuntimeError):
    pass


# [doc:mut-state]
def read_state(bus):
    """(serial, logical monitors as dicts, current mode id per connector,
    properties, monitor spec per connector)."""
    reply = bus.call_sync(BUS, PATH, IFACE, "GetCurrentState", None,
                          GLib.VariantType(STATE_TYPE), Gio.DBusCallFlags.NONE, -1, None)
    serial, monitors, logical, props = reply.unpack()
    current, specs = {}, {}
    for spec, modes, mprops in monitors:
        connector = spec[0]
        specs[connector] = tuple(spec)
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
    return serial, lms, {c: v["mode"] for c, v in current.items()}, props, specs


def _target(output):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    state = read_state(bus)
    index = layout.find_target(state[1], output)
    if index is None:
        raise MutterError(f"no active monitor for {output or 'the built-in panel'}")
    return bus, state, index


# [doc:mut-apply]
def apply_scale(target, output="", persistent=False):
    """Rescale one monitor (nearest supported scale), keep everything else.
    Temporary by default; persistent=True saves it after GNOME's confirmation.
    Returns the scale used."""
    bus, (serial, lms, modes, props, _specs), index = _target(output)
    scale = layout.pick_scale(target, lms[index]["supported"])
    if not persistent and abs(scale - lms[index]["scale"]) < 1e-4:
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
    method = METHOD_PERSISTENT if persistent else METHOD_TEMPORARY
    bus.call_sync(BUS, PATH, IFACE, "ApplyMonitorsConfig",
                  GLib.Variant(APPLY_TYPE, (serial, method, config, apply_props)),
                  None, Gio.DBusCallFlags.NONE, -1, None)
    return scale


# [doc:mut-supported]
def supported_scales(output=""):
    """Scales Mutter offers for the target monitor's current mode."""
    _bus, (_serial, lms, _modes, _props, _specs), index = _target(output)
    return sorted(lms[index]["supported"])


# [doc:mut-default]
def default_scale(output=""):
    """The scale GNOME saved for the target monitor in the current monitor
    setup (monitors.xml), or None if GNOME has not saved one."""
    _bus, (_serial, lms, _modes, _props, specs), index = _target(output)
    return monitorsxml.read_persistent_scale(specs.values(), lms[index]["connectors"][0])
