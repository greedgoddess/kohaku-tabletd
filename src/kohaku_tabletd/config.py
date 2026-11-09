"""Configuration: system defaults in /etc, per-user overrides in ~/.config."""

import os
import tomllib
from dataclasses import dataclass

SYSTEM_PATH = "/etc/kohaku-tabletd/config.toml"


# [doc:cfg-defaults]
@dataclass
class Config:
    laptop_scale: float = 2.0
    tablet_scale: float = 2.6667
    debounce_ms: int = 400
    output: str = ""         # connector, e.g. "eDP-1"; empty = built-in panel
    switch_device: str = ""  # e.g. "/dev/input/event5"; empty = auto-detect
    apply_command: str = ""  # replaces the Mutter backend; {scale} and {mode} are substituted


# [doc:cfg-paths]
def config_paths():
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return [SYSTEM_PATH, os.path.join(xdg, "kohaku-tabletd", "config.toml")]


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
            setattr(cfg, key, type(getattr(cfg, key))(value))
    return cfg
