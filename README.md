# kohaku-tabletd

One control instance for display scaling on a convertible: a user-level daemon
watches the kernel tablet-mode switch, switches the scale between a laptop and
a tablet value (default 200 % / 266 %), and exposes a D-Bus API and CLI that
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

## Configure

`/etc/kohaku-tabletd/config.toml`, overridden by
`~/.config/kohaku-tabletd/config.toml`. Keys: `laptop_scale`, `tablet_scale`,
`debounce_ms`, `output`, `switch_device`, `apply_command`. Then run
`systemctl --user restart kohaku-tabletd`.

## D-Bus

`io.github.greedgoddess.KohakuTabletd` on the session bus, object
`/io/github/greedgoddess/KohakuTabletd`: methods `Toggle`, `SetMode(s)`,
`Auto`, `Reapply` (each returns the effective mode), `Status` → `a{sv}`,
signal `ModeChanged(s mode, d scale, b manual)`.

## Develop

`make check` runs the tests. Code blocks are tagged `# [doc:<id>]`, explained in
[`docs/CODE.md`](docs/CODE.md).
