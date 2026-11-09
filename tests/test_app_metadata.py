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
