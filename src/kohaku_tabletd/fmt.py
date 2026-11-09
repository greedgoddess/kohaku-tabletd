"""Small text helpers shared by the CLI and the settings window (no GTK)."""

import datetime
import re

from . import __version__

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


# [doc:fmt-update]
def update_summary(info, now=None):
    """One line for the settings window from the daemon's update_* fields."""
    state, checked = info.get("update_state", "never"), info.get("update_checked", 0)
    stamp = f" · checked {when(checked, now)}" if checked else ""
    if state == "checking":
        return "Checking…"
    if state == "available":
        return f"Version {info.get('update_latest')} is available (you have {__version__}){stamp}"
    if state == "up-to-date":
        return f"Up to date ({__version__}){stamp}"
    if state == "no-release":
        return f"No releases published yet{stamp}"
    if state == "error":
        return f"Check failed: {info.get('update_error') or 'unknown error'}{stamp}"
    return "Not checked yet"
