# Opening the settings from a key (suggested setup)

This is a **local** setup suggestion, not part of the package: the script
below lives on your machine, outside this repository.

The goal: on the Chromebook's scale key (5th top-row key, `scale` in keyd),
a **single tap** toggles the temporary zoom and a **double tap** opens the
settings window.

keyd has no double-tap action (`timeout()` reacts to *holding* a key), so a
small helper does the timing. On a press it waits briefly; a second press in
that window opens the settings, otherwise it toggles.

## 1. Helper script

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

## 2. keyd binding

In `/etc/keyd/default.conf` under `[main]`, then `sudo keyd reload`:

```ini
scale = command(/usr/local/bin/scale-key)
```

## Notes

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
