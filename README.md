# kohaku-tabletd

One control instance for display scaling on a convertible: a user-level daemon
watches the kernel tablet-mode switch, switches between GNOME's own display scale
and a temporary zoom (default 266 %), and exposes a D-Bus API and CLI that
every other trigger (keyd, GNOME shortcuts, scripts) goes through.

Built for GNOME on Fedora (Mutter `DisplayConfig`); other setups can plug in
their own command via `apply_command`.

## Install

```sh
make rpm && sudo dnf install rpmbuild/RPMS/noarch/kohaku-tabletd-*.rpm
systemctl --user start kohaku-tabletd   # or log out and in
```

Tagged releases (`v*`) publish the RPM on GitHub Releases.

## Use

```sh
kohaku-tabletd toggle    # switch to the other mode (manual override)
kohaku-tabletd tablet    # / laptop: force a mode
kohaku-tabletd auto      # follow the hinge again
kohaku-tabletd status
```

A manual override lasts until the hinge actually changes mode. Hinge bounces
are debounced, and only the daemon ever touches the display config.

From keyd (runs as root), add `--active-user`, see `data/keyd-example.conf`:

```ini
scale = command(/usr/bin/kohaku-tabletd --active-user toggle)
```

## Settings window

"Tablet Mode" in the app grid (or `kohaku-tabletd settings`):

- **Scaling**: current state, the **default scale** and the **temporary zoom**,
  chosen from the scales GNOME offers. The default scale *is* GNOME's display
  scale: it is read from GNOME's saved configuration and changed permanently,
  so GNOME asks you to confirm (same as in GNOME Settings). The daemon switches
  between that default and the temporary zoom, which is never saved to GNOME.
- **Sources**: the last 50 trigger calls with their source (e.g. `keyd`) and
  process chain, plus a blocklist. Calls from blocked sources are refused.
- **About**: version, link to this repository, and the update check (daily
  against GitHub releases, on by default). A new release shows a desktop
  notification once; clicking it opens the release page.

Further settings get their own tab (`PAGES` in `settings_ui.py`).

## Configure

`/etc/kohaku-tabletd/config.toml`, overridden by
`~/.config/kohaku-tabletd/config.toml`. Keys: `tablet_scale` (temporary zoom), `laptop_scale` (fallback only),
`debounce_ms`, `output`, `switch_device`, `apply_command`, `blocklist`,
`update_check`. The
settings window writes the user file; for other keys run
`systemctl --user restart kohaku-tabletd` after editing.

## D-Bus

`io.github.greedgoddess.KohakuTabletd` on the session bus, object
`/io/github/greedgoddess/KohakuTabletd`: methods `Toggle`, `SetMode(s)`,
`Auto`, `Reapply` (trigger API, each returns the effective mode; blocked
sources get `…Error.Blocked`), `Status` and `GetSettings` → `a{sv}`,
`SetSettings(a{sv})`, `RecentCalls` → `a(xsssb)`, `CheckForUpdates`; signals
`ModeChanged(s mode, d scale, b manual)`, `SettingsChanged(a{sv})`,
`CallRecorded(x time_ms, s action, s source, s chain, b blocked)`.

## Develop

`make check` runs the tests. Code blocks are tagged `# [doc:<id>]`, explained in
[`docs/CODE.md`](docs/CODE.md).
