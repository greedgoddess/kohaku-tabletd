import unittest

from kohaku_tabletd import layout


def lm(x, y, scale, width=3840, height=2160, builtin=False, connector="eDP-1", transform=0):
    return {"x": x, "y": y, "scale": scale, "transform": transform, "primary": builtin,
            "connectors": [connector], "width": width, "height": height,
            "supported": [1.0, 2.0, 2.6666667461395264, 3.0], "builtin": builtin}


class LayoutTest(unittest.TestCase):
    def test_pick_nearest_supported(self):
        self.assertAlmostEqual(layout.pick_scale(2.6667, [2.0, 2.6666667461395264, 3.0]), 2.6666667, 5)
        self.assertEqual(layout.pick_scale(2.6667, [1.0, 2.0, 3.0]), 3.0)
        self.assertEqual(layout.pick_scale(2.0, []), 2.0)

    def test_find_target(self):
        lms = [lm(0, 0, 1.0, connector="DP-1"), lm(1920, 0, 2.0, builtin=True)]
        self.assertEqual(layout.find_target(lms), 1)
        self.assertEqual(layout.find_target(lms, "DP-1"), 0)
        self.assertIsNone(layout.find_target(lms, "HDMI-1"))

    def test_rescale_shifts_monitor_on_the_right(self):
        lms = [lm(0, 0, 2.0, builtin=True), lm(1920, 0, 1.0, 1920, 1080, connector="DP-1")]
        new = layout.rescale(lms, 0, 2.6666667461395264)
        self.assertEqual(layout.logical_size(new[0]), (1440, 810))
        self.assertEqual((new[1]["x"], new[1]["y"]), (1440, 0))
        self.assertEqual(lms[1]["x"], 1920)  # input untouched

    def test_rotated_size(self):
        self.assertEqual(layout.logical_size(lm(0, 0, 2.0, transform=1)), (1080, 1920))
