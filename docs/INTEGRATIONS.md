# Integrations

Integrations adjust docks, launchers or the desktop while the device is
**folded into tablet mode** (hinge position, not the manual zoom toggle), and
undo it when it is unfolded. Each one is a switch under **Integrations** in
the Tablet Mode settings window, off until you turn it on.

The daemon saves what an integration changed, so your own settings come back
when you unfold, log out, or after a crash or reboot in tablet mode.

## Included

All included integrations come with the default install and are off until
you switch them on. If the program they target isn't installed, the switch
says so and stays inactive.

| Integration | What it does |
|---|---|
| Dash to Dock (also Ubuntu Dock) | Keeps the dock always visible (`dock-fixed`), which also reserves its space so maximized and tiled windows stop at its edge. |

## Writing one

An integration is a Python module with an `INTEGRATIONS` list of
`Integration` subclasses. Put it in either place:

- `~/.local/share/kohaku-tabletd/integrations/<name>.py` for a local one
- `src/kohaku_tabletd/integrations/<name>.py` to contribute it; it then
  ships with the default install like the others

Then `systemctl --user restart kohaku-tabletd`. Broken plugins are skipped and
logged (`journalctl --user -u kohaku-tabletd`).

### GSettings-based (most docks and launchers)

```python
from kohaku_tabletd.integration import GSettingsOverride


class BigIcons(GSettingsOverride):
    id = "my-dock-big-icons"            # stable, stored in your config
    title = "Bigger dock icons"
    description = "Larger icons are easier to tap"
    category = "dock"                   # dock, launcher or desktop
    schema_id = "org.gnome.shell.extensions.dash-to-dock"
    # only needed when the schema ships inside an extension:
    schema_dirs = ("~/.local/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas",)
    overrides = {"dash-max-icon-size": 64}


INTEGRATIONS = [BigIcons]
```

The helper saves the current values when tablet mode starts and restores them
afterwards; it reports "not installed" if the schema can't be found.

### Anything else

Subclass `Integration` and implement:

- `available()` → `(ok, reason)`; `reason` is shown in the settings window
- `enter()` → applies the change and returns what is needed to undo it
  (JSON-serialisable; it is saved to disk)
- `leave(saved)` → undoes it with that data

Both run inside the daemon: keep them quick and raise an exception on failure.
That works for other desktops too, e.g. calling a panel's D-Bus API or a
command-line tool.
