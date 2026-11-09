import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from kohaku_tabletd import integration


class Recorder(integration.Integration):
    category = "dock"

    def __init__(self, id_, ok=True, fail=False):
        self.id, self.title, self.ok, self.fail = id_, id_.title(), ok, fail
        self.calls = []

    def available(self):
        return self.ok, "" if self.ok else "not installed"

    def enter(self):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append("enter")
        return {"was": "previous"}

    def leave(self, saved):
        self.calls.append(("leave", saved))


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "state", "integrations.json")

    def manager(self, enabled, items):
        return integration.IntegrationManager(enabled, items, integration.StateStore(self.path))

    def test_enters_once_and_restores(self):
        dock = Recorder("dock")
        m = self.manager(["dock"], [dock])
        self.assertTrue(m.sync(True))
        self.assertFalse(m.sync(True))
        m.sync(False)
        self.assertEqual(dock.calls, ["enter", ("leave", {"was": "previous"})])

    def test_restores_after_restart(self):
        self.manager(["dock"], [Recorder("dock")]).sync(True)
        dock = Recorder("dock")  # new daemon, still folded state on disk
        self.manager(["dock"], [dock]).sync(False)
        self.assertEqual(dock.calls, [("leave", {"was": "previous"})])

    def test_disabling_while_folded_restores(self):
        dock = Recorder("dock")
        m = self.manager(["dock"], [dock])
        m.sync(True)
        m.enabled = set()
        m.sync(True)
        self.assertEqual(dock.calls[-1], ("leave", {"was": "previous"}))

    def test_not_enabled_or_unavailable_is_left_alone(self):
        off, missing = Recorder("off"), Recorder("missing", ok=False)
        m = self.manager(["missing"], [off, missing])
        m.sync(True)
        self.assertEqual((off.calls, missing.calls), ([], []))
        rows = {row["id"]: row for row in m.describe()}
        self.assertEqual((rows["missing"]["available"], rows["missing"]["note"]), (False, "not installed"))
        self.assertFalse(rows["off"]["enabled"])

    def test_one_failure_does_not_stop_others(self):
        broken, dock = Recorder("broken", fail=True), Recorder("dock")
        m = self.manager(["broken", "dock"], [broken, dock])
        m.sync(True)
        self.assertEqual(dock.calls, ["enter"])
        self.assertEqual({r["id"]: r["note"] for r in m.describe()}["broken"], "boom")


class DiscoverTest(unittest.TestCase):
    def test_packaged_and_local_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "launcher.py"), "w") as fh:
                fh.write(textwrap.dedent("""
                    from kohaku_tabletd.integration import Integration
                    class Launcher(Integration):
                        id, title, category = "my-launcher", "My launcher", "launcher"
                    class Clash(Integration):
                        id = "dash-to-dock"
                    INTEGRATIONS = [Launcher, Clash]
                """))
            with open(os.path.join(tmp, "broken.py"), "w") as fh:
                fh.write("raise ImportError('nope')\n")
            with self.assertLogs("kohaku-tabletd", "WARNING"):
                found = integration.discover(extra_dirs=[tmp])
        ids = [i.id for i in found]
        self.assertEqual(ids, ["dash-to-dock", "my-launcher"])  # packaged wins the clash
        self.assertEqual(type(found[0]).__module__, "kohaku_tabletd.integrations.dash_to_dock")


def gio_settings_available():
    try:
        from gi.repository import Gio  # noqa: F401
    except (ImportError, ValueError):
        return False
    return shutil.which("glib-compile-schemas") is not None


@unittest.skipUnless(gio_settings_available(), "needs PyGObject and glib-compile-schemas")
class GSettingsOverrideTest(unittest.TestCase):
    """Real GSettings (memory backend) with a schema shipped like an extension's."""

    @classmethod
    def setUpClass(cls):
        os.environ["GSETTINGS_BACKEND"] = "memory"
        cls.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(cls.tmp.name, "org.example.dock.gschema.xml"), "w") as fh:
            fh.write("""<schemalist><schema id="org.example.dock" path="/org/example/dock/">
                <key name="dock-fixed" type="b"><default>false</default></key>
                <key name="icon-size" type="i"><default>48</default></key>
            </schema></schemalist>""")
        subprocess.run(["glib-compile-schemas", cls.tmp.name], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def dock(self, **attrs):
        cls = type("Dock", (integration.GSettingsOverride,), {
            "id": "example", "schema_id": "org.example.dock", "schema_dirs": (self.tmp.name,),
            "overrides": {"dock-fixed": True, "icon-size": 64}, **attrs})
        return cls()

    def test_enter_and_restore(self):
        dock = self.dock()
        settings, _ = dock._settings()
        settings.set_int("icon-size", 32)  # the user's own value
        saved = dock.enter()
        self.assertEqual((settings.get_boolean("dock-fixed"), settings.get_int("icon-size")), (True, 64))
        dock.leave(saved)
        self.assertEqual((settings.get_boolean("dock-fixed"), settings.get_int("icon-size")), (False, 32))

    def extension_dock(self, enabled, accept=True):
        calls = []
        info = {"uuid": "dock@example.com", "enabled": enabled}

        def shell(_self, method, *args):
            calls.append((method,) + args)
            if method == "GetExtensionInfo":
                return (info if args[0] == "dock@example.com" else {},)
            return (accept,)

        cls = type("ExtDock", (integration.GnomeExtensionOverride,), {
            "id": "ext", "schema_id": "org.example.dock", "schema_dirs": (self.tmp.name,),
            "overrides": {"dock-fixed": True},
            "extension_uuids": ("other@example.com", "dock@example.com"), "_shell": shell})
        return cls(), calls

    def test_extension_switched_on_only_while_folded(self):
        dock, calls = self.extension_dock(enabled=False)
        settings, _ = dock._settings()
        self.assertEqual(dock.available(), (True, ""))
        saved = dock.enter()
        self.assertIn(("EnableExtension", "dock@example.com"), calls)
        self.assertTrue(settings.get_boolean("dock-fixed"))
        dock.leave(saved)
        self.assertEqual(calls[-1], ("DisableExtension", "dock@example.com"))
        self.assertFalse(settings.get_boolean("dock-fixed"))

    def test_extension_already_on_stays_on(self):
        dock, calls = self.extension_dock(enabled=True)
        dock.leave(dock.enter())
        self.assertFalse([c for c in calls if c[0] in ("EnableExtension", "DisableExtension")])

    def test_refused_enable_rolls_back_settings(self):
        dock, _calls = self.extension_dock(enabled=False, accept=False)
        settings, _ = dock._settings()
        with self.assertRaises(RuntimeError):
            dock.enter()
        self.assertFalse(settings.get_boolean("dock-fixed"))

    def test_leave_accepts_plain_gsettings_state(self):
        dock, calls = self.extension_dock(enabled=False)
        settings, _ = dock._settings()
        settings.set_boolean("dock-fixed", True)
        dock.leave({"dock-fixed": "false"})  # written by 0.6.0
        self.assertFalse(settings.get_boolean("dock-fixed"))
        self.assertFalse([c for c in calls if c[0] == "DisableExtension"])

    def test_extension_not_installed(self):
        dock, _calls = self.extension_dock(enabled=False)
        dock.extension_uuids = ("missing@example.com",)
        self.assertEqual(dock.available(), (False, "extension not installed"))

    def test_unavailable_reasons(self):
        self.assertIn("not installed", self.dock(schema_id="org.example.none").available()[1])
        self.assertIn("missing nope", self.dock(overrides={"nope": 1}).available()[1])
        from kohaku_tabletd.integrations.dash_to_dock import DashToDock
        ok, reason = DashToDock().available()
        self.assertIsInstance(ok, bool)
        self.assertTrue(ok or "dash-to-dock" in reason)


class BuiltInTest(unittest.TestCase):
    def test_dash_to_dock_ships_in_the_base_package_and_starts_off(self):
        from pathlib import Path
        from kohaku_tabletd import config
        spec = (Path(__file__).resolve().parents[1] / "packaging" / "kohaku-tabletd.spec").read_text()
        self.assertNotIn("%package", spec)
        self.assertNotIn("%exclude", spec)
        self.assertEqual(config.Config().integrations, [])
        self.assertIn("dash-to-dock", [i.id for i in integration.discover(extra_dirs=[])])
