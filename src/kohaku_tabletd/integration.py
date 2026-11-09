"""Tablet-mode integrations: small plugins that adjust docks, launchers or the
desktop while the device is folded, and undo it when it is unfolded.

A plugin is a module with a module-level INTEGRATIONS list of Integration
subclasses, either packaged in kohaku_tabletd/integrations/ or as a local .py
file in ~/.local/share/kohaku-tabletd/integrations/. See docs/INTEGRATIONS.md."""

import glob
import importlib
import importlib.util
import json
import logging
import os
import pkgutil

log = logging.getLogger("kohaku-tabletd")
CATEGORIES = ("dock", "launcher", "desktop")


# [doc:int-base]
class Integration:
    """Base class. enter() changes things and returns what leave() needs to
    restore them (JSON-serialisable). Both run in the daemon's main loop:
    keep them quick, raise on failure."""

    id = ""            # stable, used in the config and the state file
    title = ""         # switch label in the settings window
    description = ""   # one line under the switch
    category = "desktop"  # one of CATEGORIES

    def available(self):
        """(ok, reason): can it run here? reason is shown when it can't."""
        return True, ""

    def enter(self):
        return {}

    def leave(self, saved):
        pass


# [doc:int-gsettings]
class GSettingsOverride(Integration):
    """Sets GSettings keys in tablet mode and restores the previous values.
    Subclasses set schema_id and overrides {key: value}; schema_dirs lists
    folders with a gschemas.compiled for schemas that ship inside a GNOME
    Shell extension instead of system-wide."""

    schema_id = ""
    schema_dirs = ()
    overrides = {}

    def _settings(self):
        from gi.repository import Gio, GLib

        default = Gio.SettingsSchemaSource.get_default()
        schema = default.lookup(self.schema_id, True) if default else None
        for directory in self.schema_dirs:
            if schema is not None:
                break
            directory = os.path.expanduser(directory)
            if not os.path.isfile(os.path.join(directory, "gschemas.compiled")):
                continue
            try:
                source = Gio.SettingsSchemaSource.new_from_directory(directory, default, False)
            except GLib.Error:
                continue
            schema = source.lookup(self.schema_id, False)
        if schema is None:
            return None, f"not installed (settings schema {self.schema_id} not found)"
        missing = [key for key in self.overrides if not schema.has_key(key)]
        if missing:
            return None, f"unsupported version (missing {', '.join(missing)})"
        return Gio.Settings.new_full(schema, None, None), ""

    def available(self):
        settings, reason = self._settings()
        return settings is not None, reason

    def enter(self):
        from gi.repository import Gio, GLib

        settings, reason = self._settings()
        if settings is None:
            raise RuntimeError(reason)
        saved = {key: settings.get_value(key).print_(True) for key in self.overrides}
        for key, value in self.overrides.items():
            settings.set_value(key, GLib.Variant(settings.get_value(key).get_type_string(), value))
        Gio.Settings.sync()
        return saved

    def leave(self, saved):
        from gi.repository import Gio, GLib

        settings, reason = self._settings()
        if settings is None:
            raise RuntimeError(reason)
        for key, text in saved.items():
            settings.set_value(key, GLib.Variant.parse(None, text, None, None))
        Gio.Settings.sync()


# [doc:int-store]
class StateStore:
    """Which integrations are active and what they saved, on disk so a crash
    or reboot in tablet mode still restores everything later."""

    def __init__(self, path=None):
        base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        self.path = path or os.path.join(base, "kohaku-tabletd", "integrations.json")
        try:
            with open(self.path) as fh:
                self.data = json.load(fh)
        except (OSError, ValueError):
            self.data = {}

    def get(self, integration_id):
        return self.data.get(integration_id, {})

    def put(self, integration_id, record):
        self.data[integration_id] = record
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self.data, fh)
        os.replace(tmp, self.path)


def user_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "kohaku-tabletd", "integrations")


# [doc:int-discover]
def discover(package="kohaku_tabletd.integrations", extra_dirs=None):
    """Instances of every integration found: packaged modules first, then
    local files. A plugin that fails to load is logged and skipped."""
    loaders = []
    try:
        pkg = importlib.import_module(package)
        for info in pkgutil.iter_modules(pkg.__path__):
            name = f"{package}.{info.name}"
            loaders.append((name, lambda name=name: importlib.import_module(name)))
    except ImportError:
        pass
    for directory in [user_dir()] if extra_dirs is None else extra_dirs:
        for path in sorted(glob.glob(os.path.join(directory, "*.py"))):
            def load(path=path):
                stem = os.path.splitext(os.path.basename(path))[0]
                spec = importlib.util.spec_from_file_location(f"kohaku_tabletd_local.{stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            loaders.append((path, load))
    found, seen = [], set()
    for label, load in loaders:
        try:
            for cls in getattr(load(), "INTEGRATIONS", []):
                integration = cls()
                if not integration.id or integration.id in seen:
                    log.warning("integration %s: missing or duplicate id %r", label, integration.id)
                    continue
                seen.add(integration.id)
                found.append(integration)
        except Exception as exc:  # a broken plugin must not take the daemon down
            log.warning("integration %s failed to load: %s", label, exc)
    return found


# [doc:int-manager]
class IntegrationManager:
    """Brings each integration to the right state: active exactly when the
    device is in tablet mode and the integration is enabled."""

    def __init__(self, enabled, integrations=None, store=None):
        self.enabled = set(enabled)
        self.integrations = discover() if integrations is None else list(integrations)
        self.store = store if store is not None else StateStore()
        self.errors = {}

    def sync(self, tablet):
        changed = False
        for integration in self.integrations:
            record = self.store.get(integration.id)
            active = record.get("active", False)
            want = tablet and integration.id in self.enabled
            try:
                if want and not active:
                    ok, reason = integration.available()
                    if not ok:
                        self.errors[integration.id] = reason
                        continue
                    self.store.put(integration.id, {"active": True, "saved": integration.enter()})
                    changed = True
                    log.info("integration %s: on", integration.id)
                elif active and not want:
                    integration.leave(record.get("saved", {}))
                    self.store.put(integration.id, {"active": False})
                    changed = True
                    log.info("integration %s: restored", integration.id)
                self.errors.pop(integration.id, None)
            except Exception as exc:
                self.errors[integration.id] = str(exc)
                log.warning("integration %s: %s", integration.id, exc)
        return changed

    def describe(self):
        rows = []
        for integration in self.integrations:
            try:
                ok, reason = integration.available()
            except Exception as exc:
                ok, reason = False, str(exc)
            rows.append({
                "id": integration.id, "title": integration.title or integration.id,
                "description": integration.description, "category": integration.category,
                "enabled": integration.id in self.enabled, "available": ok,
                "active": self.store.get(integration.id).get("active", False),
                "note": self.errors.get(integration.id) or reason,
            })
        return rows
