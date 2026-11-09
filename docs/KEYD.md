# Key setups (suggested, local)

These are **local** setup suggestions, not part of the package: bindings and
scripts live on your machine, outside this repository. Pick one of them for
the Chromebook's scale key (5th top-row key, `scale` in keyd).

## A. Manual trigger: one tap toggles the zoom

The simplest setup calls the trigger API directly. In `/etc/keyd/default.conf`
under `[main]`, then `sudo keyd reload`:

```ini
scale = command(/usr/bin/kohaku-tabletd --active-user toggle)
```

- `toggle` switches between GNOME's default scale and the temporary zoom as a
  manual override, which holds until the hinge actually changes mode. Use
  `tablet` or `laptop` instead to always force one mode, or `auto` to go back
  to following the hinge.
- keyd runs commands as root; `--active-user` hands the call to the session of
  whoever is logged in, so no username is hard-coded.
- In the Sources tab these calls show up as `keyd`
  (chain `keyd.service › kohaku-tabletd`); block that name to disable the key.
- Without keyd, a GNOME custom shortcut (Settings → Keyboard → Custom
  Shortcuts) with the command `kohaku-tabletd toggle` works too. It already
  runs in your session, so `--active-user` is not needed.

## B. Manual trigger plus settings: double tap opens the window

A **single tap** toggles the zoom as in A, a **double tap** opens the
settings window instead.

keyd has no double-tap action (`timeout()` reacts to *holding* a key), so a
small helper does the timing. On a press it waits briefly; a second press in
that window opens the settings, otherwise it toggles.

### Helper script

Save as `/usr/local/bin/scale-key` and make it executable
(`sudo chmod 755 /usr/local/bin/scale-key`):

```bash
#!/bin/bash
# Local keyd helper (not part of kohaku-tabletd).
# Scale key: single tap toggles the zoom, double tap opens the settings window.
set -u

WINDOW_MS=350
STAMP=/run/scale-key.pending
LOCK=/run/lock/scale-key.lock

now_ms() { date +%s%3N; }

active_user() {
    local session
    session=$(loginctl show-seat seat0 -p ActiveSession --value) && [[ -n $session ]] &&
        loginctl show-session "$session" -p Name --value
}

open_settings() {
    local user
    user=$(active_user) || exit 1
    systemd-run --user --machine="$user@.host" --collect --quiet \
        /usr/bin/kohaku-tabletd settings
}

toggle() {
    /usr/bin/kohaku-tabletd --active-user toggle
}

exec 9>"$LOCK"
flock 9
if read -r ts _ 2>/dev/null <"$STAMP" && (( $(now_ms) - ts <= WINDOW_MS )); then
    rm -f "$STAMP"
    exec 9>&-
    open_settings
    exit
fi
echo "$(now_ms) $$" >"$STAMP"
exec 9>&-

sleep "$(printf '0.%03d' "$WINDOW_MS")"

exec 9>"$LOCK"
flock 9
if read -r _ pid 2>/dev/null <"$STAMP" && [[ $pid == "$$" ]]; then
    rm -f "$STAMP"
    exec 9>&-
    toggle
fi
```

### keyd binding

In `/etc/keyd/default.conf` under `[main]`, then `sudo keyd reload`:

```ini
scale = command(/usr/local/bin/scale-key)
```

### Notes

- **Timing:** single taps act after `WINDOW_MS` (350 ms), the time the script
  waits for a second tap. Lower it for snappier toggles, raise it if double
  taps get missed.
- **Why `systemd-run`:** keyd runs commands as root. Starting the window
  through your systemd user manager gives it your display and session bus.
  A second double tap while the window is open just brings it forward.
- **Sources tab:** toggles from this key show up as `scale-key`
  (chain `keyd › scale-key › kohaku-tabletd`); block that name to disable
  the key.
- **Other ways to open the settings:** "Tablet Mode" in the app grid,
  `kohaku-tabletd settings` in a terminal, or a GNOME custom shortcut
  (Settings → Keyboard → Custom Shortcuts) with that command.

To go back from B to A, point the binding at `kohaku-tabletd` again as shown
in A and remove `/usr/local/bin/scale-key`.
