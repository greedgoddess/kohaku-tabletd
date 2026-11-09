# Code map

Each `# [doc:<id>]` comment in the code points here (`docs/CODE.md#<id>`).
`tests/test_doc_tags.py` checks that tags and entries match and IDs are unique.

## `src/kohaku_tabletd/__init__.py`

| ID | What it does |
|---|---|
| <a id="pkg-bus-names"></a>`pkg-bus-names` | D-Bus name, object path, interface, settings app id, and the source name used for hinge events. |

## `src/kohaku_tabletd/config.py`

| ID | What it does |
|---|---|
| <a id="cfg-defaults"></a>`cfg-defaults` | All settings and their defaults (266 % temporary zoom, 200 % fallback default, 400 ms debounce, empty blocklist, update check on). The real default scale is GNOME's own (monitors.xml). |
| <a id="cfg-paths"></a>`cfg-paths` | Lookup order: `/etc/kohaku-tabletd/config.toml`, then `~/.config/kohaku-tabletd/config.toml`. |
| <a id="cfg-load"></a>`cfg-load` | Merges files (later wins), coerces types, rejects unknown keys and non-string blocklists. |
| <a id="cfg-validate"></a>`cfg-validate` | Checks settings changes from D-Bus: default scale and temporary zoom (1–4), the blocklist (deduped, sorted), the update-check switch. |
| <a id="cfg-toml"></a>`cfg-toml` | Minimal TOML writer for the flat user config (strings, numbers, lists). |
| <a id="cfg-save"></a>`cfg-save` | Merges changes into the user config, keeping other keys; writes atomically. |

## `src/kohaku_tabletd/callers.py`

| ID | What it does |
|---|---|
| <a id="call-proc"></a>`call-proc` | Reads parent PID and argv of a process from `/proc`. |
| <a id="call-name"></a>`call-name` | Readable process name; for interpreters and shells, the script they run. |
| <a id="call-unit"></a>`call-unit` | Reads the caller's systemd unit from its cgroup and turns it into a source name (`keyd.service` → `keyd`, `app-gnome-<app id>-<n>.scope` → app id). |
| <a id="call-identify"></a>`call-identify` | Walks up from the caller past our own CLI, `sh -c` wrappers and launchers; if that leads nowhere (keyd detaches its commands), the unit names the source. |

## `src/kohaku_tabletd/monitorsxml.py`

| ID | What it does |
|---|---|
| <a id="mx-paths"></a>`mx-paths` | Where GNOME keeps saved display configs: `~/.config/monitors.xml`, then `/etc/xdg/monitors.xml`. |
| <a id="mx-scale"></a>`mx-scale` | Finds the saved configuration for exactly the connected monitors and returns the panel's scale. |

## `src/kohaku_tabletd/fmt.py`

| ID | What it does |
|---|---|
| <a id="fmt-helpers"></a>`fmt-helpers` | Shared text helpers: strip GDBus error prefixes, scales as percent, nearest supported scale, call timestamps. |
| <a id="fmt-update"></a>`fmt-update` | One-line update status for the About tab. |

## `src/kohaku_tabletd/updates.py`

| ID | What it does |
|---|---|
| <a id="upd-version"></a>`upd-version` | Parses release tags (`v0.3.0`, `0.3.0-rc1`) and compares them with the installed version. |
| <a id="upd-fetch"></a>`upd-fetch` | Asks the GitHub API for the latest release; a 404 means nothing is published yet. |
| <a id="upd-check"></a>`upd-check` | One check as a result dict (`available`, `up-to-date`, `no-release`, `error`); never raises. |
| <a id="upd-state"></a>`upd-state` | Last result and last notified version in `~/.local/state/kohaku-tabletd/update.json`. |

## `src/kohaku_tabletd/state.py`

| ID | What it does |
|---|---|
| <a id="st-model"></a>`st-model` | Mode state: physical (hinge) mode plus optional manual override; effective = override or physical. |
| <a id="st-hinge"></a>`st-hinge` | Only a real hinge transition counts, and it clears the override. Repeated readings are ignored. |
| <a id="st-manual"></a>`st-manual` | Manual control: set / toggle create an override, auto removes it. |

## `src/kohaku_tabletd/layout.py`

| ID | What it does |
|---|---|
| <a id="lay-pick"></a>`lay-pick` | Picks the supported scale nearest to the configured one. |
| <a id="lay-size"></a>`lay-size` | Logical size of a monitor, honouring rotation and layout mode. |
| <a id="lay-target"></a>`lay-target` | Chooses the monitor to rescale: configured connector or the built-in panel. |
| <a id="lay-rescale"></a>`lay-rescale` | Rescales one monitor and shifts monitors right of / below it by the size change. |

## `src/kohaku_tabletd/switch.py`

| ID | What it does |
|---|---|
| <a id="sw-find"></a>`sw-find` | Finds the evdev node advertising `SW_TABLET_MODE` via sysfs; prefers the one named "Tablet Mode Switch" (Chromebook EC). |
| <a id="sw-read"></a>`sw-read` | Reads the current switch state with the `EVIOCGSW` ioctl. |
| <a id="sw-open"></a>`sw-open` | Opens the configured or detected device non-blocking. |
| <a id="sw-drain"></a>`sw-drain` | Consumes queued events, reports whether the tablet switch fired, raises when the device is gone. |

## `src/kohaku_tabletd/mutter.py`

| ID | What it does |
|---|---|
| <a id="mut-state"></a>`mut-state` | Reads `GetCurrentState` and flattens it into logical monitors, current mode ids and monitor specs. |
| <a id="mut-apply"></a>`mut-apply` | Applies a scale via `ApplyMonitorsConfig`, keeping modes, transforms, primary and layout mode. Temporary for switching (no dialog, no-op if unchanged); persistent for the default (GNOME's keep-changes dialog, saved on confirm). |
| <a id="mut-default"></a>`mut-default` | GNOME's saved scale for the panel in the current monitor setup, via `monitorsxml`. |
| <a id="mut-supported"></a>`mut-supported` | Lists the scales Mutter offers for the target monitor (feeds the settings dropdowns). |

## `src/kohaku_tabletd/daemon.py`

| ID | What it does |
|---|---|
| <a id="dmn-iface"></a>`dmn-iface` | D-Bus interface: trigger methods (`Toggle`, `SetMode`, `Auto`, `Reapply`), `Status`, `GetSettings`/`SetSettings`, `RecentCalls`, `CheckForUpdates`; signals `ModeChanged`, `SettingsChanged`, `CallRecorded`. |
| <a id="dmn-apply"></a>`dmn-apply` | Applies the effective mode's scale (laptop: GNOME's default, tablet: temporary zoom) via Mutter or `apply_command`, then emits `ModeChanged`. |
| <a id="dmn-default"></a>`dmn-default` | Reads the default from GNOME (fallback `laptop_scale`); changing it applies a persistent config and marks it pending until GNOME's dialog is answered. |
| <a id="dmn-display-watch"></a>`dmn-display-watch` | Watches Mutter's `MonitorsChanged` and `monitors.xml`: clears the pending default (confirmed or reverted), refreshes listeners, and restores the temporary zoom if GNOME saved a config while in tablet mode. |
| <a id="dmn-record"></a>`dmn-record` | Keeps the last 50 triggers in memory and emits `CallRecorded`. |
| <a id="dmn-identify"></a>`dmn-identify` | Resolves a D-Bus sender to its PID, then to source and chain via `callers`. |
| <a id="dmn-switch-attach"></a>`dmn-switch-attach` | Opens the switch, records its state, watches the fd; retries every 10 s if missing. |
| <a id="dmn-switch-event"></a>`dmn-switch-event` | On switch events, (re)starts the debounce timer; on device loss, reattaches. |
| <a id="dmn-debounce"></a>`dmn-debounce` | After the hinge settles, reads the real state once; on a transition records it (source `hinge`) and applies. |
| <a id="dmn-dbus-methods"></a>`dmn-dbus-methods` | Dispatches method calls; invalid input, file and apply failures become D-Bus errors. |
| <a id="dmn-trigger"></a>`dmn-trigger` | Trigger API: identifies and records the caller, refuses blocklisted sources with `Error.Blocked`, otherwise acts. |
| <a id="dmn-settings"></a>`dmn-settings` | Settings over D-Bus: default scale (+ pending flag), temporary zoom, supported scales, blocklist, update status. The default goes to GNOME, the rest to the user config; the zoom is reapplied if active. |
| <a id="dmn-updates"></a>`dmn-updates` | Update checks in a worker thread: on demand, 60 s after start and hourly once the last check is a day old (if enabled); results are saved and broadcast. |
| <a id="dmn-notify"></a>`dmn-notify` | Desktop notification (app icon, linked to the desktop entry) once per new version; clicking it opens the release page. |
| <a id="dmn-run"></a>`dmn-run` | Exports the object, owns the bus name (single instance), handles SIGINT/SIGTERM. |

## `src/kohaku_tabletd/cli.py`

| ID | What it does |
|---|---|
| <a id="cli-commands"></a>`cli-commands` | CLI subcommands and the D-Bus method each one calls. |
| <a id="cli-active-user"></a>`cli-active-user` | `--active-user` as root: finds the active seat0 session via logind and drops to that user's session bus. |
| <a id="cli-call"></a>`cli-call` | Calls the daemon (D-Bus activation starts it if needed) and prints the result. |
| <a id="cli-main"></a>`cli-main` | Argument parsing; `daemon` runs the service, `settings` opens the window, everything else is a client call. |

## `src/kohaku_tabletd/settings_ui.py`

| ID | What it does |
|---|---|
| <a id="ui-client"></a>`ui-client` | D-Bus proxy to the daemon (activation starts it if needed). |
| <a id="ui-page-base"></a>`ui-page-base` | Base class for a tab: daemon client, error toasts, signal hook. |
| <a id="ui-scaling"></a>`ui-scaling` | Scaling tab: current mode, GNOME's default scale (shows when GNOME is waiting for confirmation) and the temporary zoom. |
| <a id="ui-scale-rows"></a>`ui-scale-rows` | Dropdowns of supported scales, or spin rows when none are reported. |
| <a id="ui-sources"></a>`ui-sources` | Sources tab: recent calls and the blocklist, updated live from daemon signals. |
| <a id="ui-recent"></a>`ui-recent` | Recent-call rows (newest first) with a Block/Unblock button; hinge rows have none. |
| <a id="ui-blocklist"></a>`ui-blocklist` | Blocklist rows with remove buttons and an entry row to add a name. |
| <a id="ui-about"></a>`ui-about` | About tab: app icon header, version, GitHub link, update-check switch, status with Check now / Open release. |
| <a id="ui-pages"></a>`ui-pages` | Tab registry; future settings are added here as new `Page` subclasses. |
| <a id="ui-window"></a>`ui-window` | Window: view switcher over the tabs, toast overlay, forwards daemon signals to tabs. |
| <a id="ui-app"></a>`ui-app` | Single-instance app with the app icon as window icon; shows an error page if the daemon is unreachable. |

## `bin/kohaku-tabletd.in`

| ID | What it does |
|---|---|
| <a id="bin-launcher"></a>`bin-launcher` | Launcher template; `make install` fills in the private library dir. |

## `data/kohaku-tabletd.service`

| ID | What it does |
|---|---|
| <a id="unit-session"></a>`unit-session` | User unit tied to `graphical-session.target`; `Type=dbus` so it counts as ready once it owns its name. |

## `data/io.github.greedgoddess.KohakuTabletd.Settings.desktop`

| ID | What it does |
|---|---|
| <a id="app-desktop"></a>`app-desktop` | App-grid entry "Tablet Mode" with the app icon; its name is the app id, which GNOME uses to match the window, notifications and AppStream metadata. |

## `data/70-kohaku-tabletd.rules`

| ID | What it does |
|---|---|
| <a id="udv-uaccess"></a>`udv-uaccess` | Gives the active seat user access to switch devices so the daemon needs no root. |

## `packaging/kohaku-tabletd.spec`

| ID | What it does |
|---|---|
| <a id="spec-check"></a>`spec-check` | Runs the tests and validates the desktop entry and AppStream metadata during the RPM build. |
| <a id="spec-post"></a>`spec-post` | Enables the user unit via preset, reloads udev rules and re-triggers switch devices. |

## `Makefile`

| ID | What it does |
|---|---|
| <a id="mk-install"></a>`mk-install` | Installs code, launcher, units, D-Bus activation, udev rule, default config, desktop entry, AppStream metadata and icons (honours `DESTDIR`). |
| <a id="mk-check"></a>`mk-check` | Runs the test suite. |
| <a id="mk-rpm"></a>`mk-rpm` | Builds a source tarball from `HEAD` and the RPM into `./rpmbuild`. |
