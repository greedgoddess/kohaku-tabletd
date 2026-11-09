"""Small text helpers shared by the CLI and the settings window (no GTK)."""

import datetime
import re

_REMOTE = re.compile(r"^GDBus\.Error:\S+:\s*")


# [doc:fmt-helpers]
def remote_error(message):
    """Drop GDBus's "GDBus.Error:<name>: " prefix from an error message."""
    return _REMOTE.sub("", message)


def percent(scale):
    return f"{scale * 100:.2f}".rstrip("0").rstrip(".") + " %"


def nearest_index(values, target):
    return min(range(len(values)), key=lambda i: abs(values[i] - target))


def when(time_ms, now=None):
    moment = datetime.datetime.fromtimestamp(time_ms / 1000)
    now = now or datetime.datetime.now()
    return moment.strftime("%H:%M:%S" if moment.date() == now.date() else "%b %d %H:%M")
