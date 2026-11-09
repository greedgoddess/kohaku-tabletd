"""Dash to Dock (and Ubuntu Dock): keep the dock visible in tablet mode.
Built in; off until enabled under Integrations in the settings window."""

from ..integration import GSettingsOverride

UUIDS = ("dash-to-dock@micxgx.gmail.com", "ubuntu-dock@ubuntu.com")


# [doc:d2d-integration]
class DashToDock(GSettingsOverride):
    """dock-fixed makes the dock always visible and reserves its space, so
    maximized and tiled windows stop at its edge."""

    id = "dash-to-dock"
    title = "Always show Dash to Dock"
    description = "Keeps the dock visible and reserves its space, so windows don't cover it"
    category = "dock"
    schema_id = "org.gnome.shell.extensions.dash-to-dock"
    schema_dirs = tuple(f"{base}/gnome-shell/extensions/{uuid}/schemas"
                        for base in ("~/.local/share", "/usr/share") for uuid in UUIDS)
    overrides = {"dock-fixed": True}


INTEGRATIONS = [DashToDock]
