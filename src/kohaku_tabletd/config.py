"""Configuration: system defaults in /etc, per-user overrides in ~/.config."""

import json
import os
import tomllib
from dataclasses import dataclass, field

SYSTEM_PATH = "/etc/kohaku-tabletd/config.toml"
EDITABLE = ("laptop_scale", "tablet_scale", "blocklist")  # changeable over D-Bus


# [doc:cfg-defaults]
@dataclass
class Config:
    laptop_scale: float = 2.0    # "default scale" in the settings window
    tablet_scale: float = 2.6667  # "temporary scale": tablet mode and shortcut override
    debounce_ms: int = 400
    output: str = ""         # connector, e.g. "eDP-1"; empty = built-in panel
    switch_device: str = ""  # e.g. "/dev/input/event5"; empty = auto-detect
    apply_command: str = ""  # replaces the Mutter backend; {scale} and {mode} are substituted
    blocklist: list = field(default_factory=list)  # caller sources the trigger API refuses


# [doc:cfg-paths]
def config_paths():
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return [SYSTEM_PATH, os.path.join(xdg, "kohaku-tabletd", "config.toml")]


def _coerce(key, value, current):
    if isinstance(current, list):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError(f"{key} must be a list of strings")
        return list(value)
    return type(current)(value)


# [doc:cfg-load]
def load(paths=None):
    """Merge the files in order (later wins). Unknown keys are an error."""
    cfg = Config()
    for path in paths if paths is not None else config_paths():
        try:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
        except FileNotFoundError:
            continue
        for key, value in data.items():
            if not hasattr(cfg, key):
                raise ValueError(f"{path}: unknown key {key!r}")
            setattr(cfg, key, _coerce(key, value, getattr(cfg, key)))
    return cfg


# [doc:cfg-validate]
def validate_update(update):
    """Check a settings change coming in over D-Bus; returns the cleaned values."""
    clean = {}
    for key, value in update.items():
        if key not in EDITABLE:
            raise ValueError(f"{key!r} cannot be changed at runtime")
        if key.endswith("_scale"):
            value = float(value)
            if not 1.0 <= value <= 4.0:
                raise ValueError(f"{key} must be between 1 and 4")
        else:
            if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
                raise ValueError("blocklist must be a list of names")
            value = sorted({v.strip() for v in value if v.strip()})
        clean[key] = value
    return clean


# [doc:cfg-toml]
def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)  # JSON string escapes are valid TOML basic strings
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"cannot write {type(value).__name__} to TOML")


def dumps(data):
    lines = ["# Managed by kohaku-tabletd (settings window); manual edits are kept.\n"]
    lines += [f"{key} = {_toml_value(value)}\n" for key, value in sorted(data.items())]
    return "".join(lines)


# [doc:cfg-save]
def save_user(update, path=None):
    """Merge `update` into the user config file, keeping its other keys. Atomic."""
    path = path or config_paths()[-1]
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        data = {}
    data.update(update)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(dumps(data))
    os.replace(tmp, path)
