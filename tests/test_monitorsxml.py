import os
import tempfile
import unittest

from kohaku_tabletd import monitorsxml

PANEL = ("eDP-1", "SDC", "0x4161", "0x00000000")
EXTERNAL = ("DP-1", "DEL", "U2720Q", "ABC123")


def spec(connector, vendor, product, serial):
    return (f"<monitorspec><connector>{connector}</connector><vendor>{vendor}</vendor>"
            f"<product>{product}</product><serial>{serial}</serial></monitorspec>")


XML = f"""<monitors version="2">
  <configuration>
    <logicalmonitor><x>0</x><y>0</y><scale>2</scale><primary>yes</primary>
      <monitor>{spec(*PANEL)}<mode><width>3840</width><height>2160</height><rate>60.001</rate></mode></monitor>
    </logicalmonitor>
  </configuration>
  <configuration>
    <logicalmonitor><x>0</x><y>0</y><scale>1.5</scale>
      <monitor>{spec(*EXTERNAL)}<mode><width>3840</width><height>2160</height><rate>60</rate></mode></monitor>
    </logicalmonitor>
    <logicalmonitor><x>2560</x><y>0</y><scale>2.6666667461395264</scale><primary>yes</primary>
      <monitor>{spec(*PANEL)}<mode><width>3840</width><height>2160</height><rate>60.001</rate></mode></monitor>
    </logicalmonitor>
  </configuration>
</monitors>"""


class MonitorsXmlTest(unittest.TestCase):
    def test_matches_the_exact_monitor_set(self):
        self.assertEqual(monitorsxml.persistent_scale(XML, [PANEL], "eDP-1"), 2.0)
        self.assertAlmostEqual(monitorsxml.persistent_scale(XML, [PANEL, EXTERNAL], "eDP-1"), 2.6666667, 5)

    def test_unknown_setup(self):
        self.assertIsNone(monitorsxml.persistent_scale(XML, [("HDMI-1", "X", "Y", "Z")], "eDP-1"))
        self.assertIsNone(monitorsxml.persistent_scale(XML, [PANEL], "DP-1"))

    def test_read_falls_through_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken, good = os.path.join(tmp, "a.xml"), os.path.join(tmp, "b.xml")
            with open(broken, "w") as fh:
                fh.write("<monitors")
            with open(good, "w") as fh:
                fh.write(XML)
            paths = [os.path.join(tmp, "missing.xml"), broken, good]
            self.assertEqual(monitorsxml.read_persistent_scale([PANEL], "eDP-1", paths), 2.0)
