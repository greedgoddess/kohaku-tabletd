# Triggering a switch

Every manual switch is a call to the daemon's trigger API. Each call shows up
in the settings window under **Sources → Recent calls**, with its source and
process chain, and can be refused there via the blocklist.

## Commands

```sh
kohaku-tabletd toggle    # switch to the other mode (manual override)
kohaku-tabletd tablet    # force the temporary zoom
kohaku-tabletd laptop    # force GNOME's default scale
kohaku-tabletd auto      # drop the override, follow the hinge again
kohaku-tabletd reapply   # apply the current mode's scale again
```

A manual override holds until the hinge actually changes mode.

## From a terminal or script

Run any command above. In Recent calls the source is the shell (`bash`) or
the script's name.

## From a key with keyd (suggested, local)

keyd runs commands as root, so add `--active-user`: it hands the call to the
session of whoever is logged in. For the Chromebook's scale key (5th top-row
key, `scale` in keyd), in `/etc/keyd/default.conf` under `[main]`:

```ini
scale = command(/usr/bin/kohaku-tabletd --active-user toggle)
```

Then `sudo keyd reload`. These calls show up as `keyd`
(chain `keyd.service › kohaku-tabletd`).

## From a GNOME shortcut

Settings → Keyboard → Custom Shortcuts, command `kohaku-tabletd toggle`. It
runs in your session, so `--active-user` is not needed.

## Over D-Bus

```sh
gdbus call --session --dest io.github.greedgoddess.KohakuTabletd \
  --object-path /io/github/greedgoddess/KohakuTabletd \
  --method io.github.greedgoddess.KohakuTabletd.Toggle
```

`SetMode` (`"tablet"`/`"laptop"`), `Auto` and `Reapply` work the same way.
Blocked sources get the error `io.github.greedgoddess.KohakuTabletd.Error.Blocked`.
