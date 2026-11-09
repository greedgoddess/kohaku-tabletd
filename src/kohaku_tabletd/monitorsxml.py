"""Read the display configuration GNOME saved permanently (monitors.xml)."""

import os
import xml.etree.ElementTree as ET

SPEC_FIELDS = ("connector", "vendor", "product", "serial")


# [doc:mx-paths]
def config_paths():
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return [os.path.join(xdg, "monitors.xml"), "/etc/xdg/monitors.xml"]


def _spec(element):
    return tuple((element.findtext(field) or "").strip() for field in SPEC_FIELDS)


# [doc:mx-scale]
def persistent_scale(xml_text, monitors, connector):
    """Scale saved for `connector` in the configuration whose monitor set
    (enabled and disabled) is exactly `monitors` (spec tuples). None if absent."""
    wanted = set(monitors)
    for conf in ET.fromstring(xml_text).iter("configuration"):
        if {_spec(s) for s in conf.iter("monitorspec")} != wanted:
            continue
        for logical in conf.findall("logicalmonitor"):
            if any(_spec(s)[0] == connector for s in logical.iter("monitorspec")):
                return float(logical.findtext("scale") or 1)
    return None


def read_persistent_scale(monitors, connector, paths=None):
    """First saved scale found in the user, then the system monitors.xml."""
    for path in paths or config_paths():
        try:
            with open(path) as fh:
                scale = persistent_scale(fh.read(), monitors, connector)
        except (OSError, ET.ParseError, ValueError):
            continue
        if scale is not None:
            return scale
    return None
