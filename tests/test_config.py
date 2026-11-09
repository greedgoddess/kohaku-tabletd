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
