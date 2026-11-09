import os
import tempfile
import unittest

from kohaku_tabletd import config


class ConfigTest(unittest.TestCase):
    def write(self, text):
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_later_file_wins_and_types_are_coerced(self):
        system = self.write("tablet_scale = 3\nlaptop_scale = 1.5\n")
        user = self.write("tablet_scale = 2.5\n")
        cfg = config.load([system, user, "/nonexistent.toml"])
        self.assertEqual((cfg.laptop_scale, cfg.tablet_scale), (1.5, 2.5))
        self.assertIsInstance(cfg.tablet_scale, float)

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            config.load([self.write("tablet_scal = 3\n")])

    def test_shipped_default_file_parses(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(config.load([os.path.join(here, "data", "config.toml")]), config.Config())


class SettingsWriteTest(unittest.TestCase):
    def test_validate(self):
        clean = config.validate_update({"tablet_scale": 2.5, "blocklist": [" keyd", "keyd", "", "x"]})
        self.assertEqual(clean, {"tablet_scale": 2.5, "blocklist": ["keyd", "x"]})
        for bad in ({"debounce_ms": 10}, {"laptop_scale": 9.0}, {"blocklist": "keyd"}):
            with self.assertRaises(ValueError):
                config.validate_update(bad)

    def test_save_user_merges_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "config.toml")
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as fh:
                fh.write('output = "eDP-1"\n')
            config.save_user({"tablet_scale": 2.6666667461395264, "blocklist": ['we"ird', "keyd"]}, path)
            cfg = config.load([path])
            self.assertEqual(cfg.output, "eDP-1")
            self.assertEqual(cfg.tablet_scale, 2.6666667461395264)
            self.assertEqual(cfg.blocklist, ['we"ird', "keyd"])

    def test_blocklist_type_checked_on_load(self):
        fd, path = tempfile.mkstemp(suffix=".toml")
        with os.fdopen(fd, "w") as fh:
            fh.write('blocklist = "keyd"\n')
        self.addCleanup(os.unlink, path)
        with self.assertRaises(ValueError):
            config.load([path])
