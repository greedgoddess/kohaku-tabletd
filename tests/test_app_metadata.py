"""The desktop entry, icons and AppStream metadata all describe the same app."""

import configparser
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from kohaku_tabletd import SETTINGS_APP_ID, __version__

DATA = Path(__file__).resolve().parents[1] / "data"


class AppMetadataTest(unittest.TestCase):
    def setUp(self):
        self.desktop = configparser.ConfigParser(interpolation=None)
        self.desktop.optionxform = str
        self.desktop.read(DATA / f"{SETTINGS_APP_ID}.desktop")
        self.entry = self.desktop["Desktop Entry"]
        self.meta = ET.parse(DATA / f"{SETTINGS_APP_ID}.metainfo.xml").getroot()

    def test_desktop_entry(self):
        self.assertEqual(self.entry["Exec"], "kohaku-tabletd settings")
        self.assertEqual(self.entry["Icon"], SETTINGS_APP_ID)

    def test_icons_exist_and_are_svg(self):
        for name in (SETTINGS_APP_ID, SETTINGS_APP_ID + "-symbolic"):
            root = ET.parse(DATA / "icons" / f"{name}.svg").getroot()
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_metainfo_matches(self):
        self.assertEqual(self.meta.findtext("id"), SETTINGS_APP_ID)
        self.assertEqual(self.meta.findtext("launchable"), f"{SETTINGS_APP_ID}.desktop")
        self.assertEqual(self.meta.findtext("name"), self.entry["Name"])

    def test_latest_release_is_current_version(self):
        self.assertEqual(self.meta.find("releases/release").get("version"), __version__)


class SpecFilesTest(unittest.TestCase):
    def test_check_section_only_runs_commands(self):
        spec = (DATA.parent / "packaging" / "kohaku-tabletd.spec").read_text()
        check = spec.split("%check\n", 1)[1].split("\n\n", 1)[0]
        for line in check.splitlines():
            self.assertFalse(line.startswith("%{"), f"stray path in %check: {line}")

    def test_files_lists_app_metadata(self):
        spec = (DATA.parent / "packaging" / "kohaku-tabletd.spec").read_text()
        files = spec.split("%files\n", 1)[1].split("\n\n", 1)[0]
        for suffix in (f"applications/{SETTINGS_APP_ID}.desktop",
                       f"{SETTINGS_APP_ID}.metainfo.xml",
                       f"scalable/apps/{SETTINGS_APP_ID}.svg",
                       f"symbolic/apps/{SETTINGS_APP_ID}-symbolic.svg"):
            self.assertTrue(any(line.endswith(suffix) for line in files.splitlines()), suffix)
