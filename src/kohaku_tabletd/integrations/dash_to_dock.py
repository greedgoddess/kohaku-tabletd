"""Dash to Dock (and Ubuntu Dock): show the dock in tablet mode.
Built in; off until enabled under Integrations in the settings window."""

from ..integration import GnomeExtensionOverride

UUIDS = ("dash-to-dock@micxgx.gmail.com", "ubuntu-dock@ubuntu.com")


# [doc:d2d-integration]
class DashToDock(GnomeExtensionOverride):
    """While folded: switch the extension on if it is off, and set dock-fixed
    so the dock is always visible and reserves its space (maximized and tiled
    windows stop at its edge). Unfolding restores both."""

    id = "dash-to-dock"
    title = "Show Dash to Dock in tablet mode"
    description = ("Turns the dock on if it is off and keeps it visible, reserving its space; "
                   "unfolding restores your setup")
    category = "dock"
    schema_id = "org.gnome.shell.extensions.dash-to-dock"
    schema_dirs = tuple(f"{base}/gnome-shell/extensions/{uuid}/schemas"
                        for base in ("~/.local/share", "/usr/share") for uuid in UUIDS)
    overrides = {"dock-fixed": True}
    extension_uuids = UUIDS


INTEGRATIONS = [DashToDock]
