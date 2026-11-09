# Code map

Each `# [doc:<id>]` comment in the code points here (`docs/CODE.md#<id>`).
`tests/test_doc_tags.py` checks that tags and entries match and IDs are unique.

## `src/kohaku_tabletd/__init__.py`

| ID | What it does |
|---|---|
| <a id="pkg-bus-names"></a>`pkg-bus-names` | D-Bus name, object path and interface shared by the daemon and CLI. |

## `src/kohaku_tabletd/config.py`

| ID | What it does |
|---|---|
| <a id="cfg-defaults"></a>`cfg-defaults` | All settings and their defaults (200 % laptop, 266 % tablet, 400 ms debounce). |
| <a id="cfg-paths"></a>`cfg-paths` | Lookup order: `/etc/kohaku-tabletd/config.toml`, then `~/.config/kohaku-tabletd/config.toml`. |
| <a id="cfg-load"></a>`cfg-load` | Merges files (later wins), coerces types, rejects unknown keys. |

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
| <a id="mut-state"></a>`mut-state` | Reads `GetCurrentState` and flattens it into logical monitors and current mode ids. |
| <a id="mut-apply"></a>`mut-apply` | Applies the new scale persistently via `ApplyMonitorsConfig`, keeping modes, transforms, primary and layout mode; no-op if unchanged. |

## `src/kohaku_tabletd/daemon.py`

| ID | What it does |
|---|---|
| <a id="dmn-iface"></a>`dmn-iface` | D-Bus interface: `Toggle`, `SetMode`, `Auto`, `Reapply`, `Status`, signal `ModeChanged`. |
| <a id="dmn-apply"></a>`dmn-apply` | Applies the effective mode's scale via Mutter or `apply_command`, then emits `ModeChanged`. The only place a scale is set. |
| <a id="dmn-switch-attach"></a>`dmn-switch-attach` | Opens the switch, records its state, watches the fd; retries every 10 s if missing. |
| <a id="dmn-switch-event"></a>`dmn-switch-event` | On switch events, (re)starts the debounce timer; on device loss, reattaches. |
| <a id="dmn-debounce"></a>`dmn-debounce` | After the hinge settles, reads the real state once and applies on a transition. |
| <a id="dmn-dbus-methods"></a>`dmn-dbus-methods` | Handles method calls; invalid input and apply failures become D-Bus errors. |
| <a id="dmn-run"></a>`dmn-run` | Exports the object, owns the bus name (single instance), handles SIGINT/SIGTERM. |

## `src/kohaku_tabletd/cli.py`

| ID | What it does |
|---|---|
| <a id="cli-commands"></a>`cli-commands` | CLI subcommands and the D-Bus method each one calls. |
| <a id="cli-active-user"></a>`cli-active-user` | `--active-user` as root: finds the active seat0 session via logind and drops to that user's session bus. |
| <a id="cli-call"></a>`cli-call` | Calls the daemon (D-Bus activation starts it if needed) and prints the result. |
| <a id="cli-main"></a>`cli-main` | Argument parsing; `daemon` runs the service, everything else is a client call. |

## `bin/kohaku-tabletd.in`

| ID | What it does |
|---|---|
| <a id="bin-launcher"></a>`bin-launcher` | Launcher template; `make install` fills in the private library dir. |

## `data/kohaku-tabletd.service`

| ID | What it does |
|---|---|
| <a id="unit-session"></a>`unit-session` | User unit tied to `graphical-session.target`; `Type=dbus` so it counts as ready once it owns its name. |

## `data/70-kohaku-tabletd.rules`

| ID | What it does |
|---|---|
| <a id="udv-uaccess"></a>`udv-uaccess` | Gives the active seat user access to switch devices so the daemon needs no root. |

## `packaging/kohaku-tabletd.spec`

| ID | What it does |
|---|---|
| <a id="spec-post"></a>`spec-post` | Enables the user unit via preset, reloads udev rules and re-triggers switch devices. |

## `Makefile`

| ID | What it does |
|---|---|
| <a id="mk-install"></a>`mk-install` | Installs code, launcher, units, D-Bus activation, udev rule and default config (honours `DESTDIR`). |
| <a id="mk-check"></a>`mk-check` | Runs the test suite. |
| <a id="mk-rpm"></a>`mk-rpm` | Builds a source tarball from `HEAD` and the RPM into `./rpmbuild`. |
