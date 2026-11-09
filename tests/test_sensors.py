import os
import tempfile
import unittest

from kohaku_tabletd import sensors

STUCK = (-223, -450, 8390)


def lid(i):
    """A lid accelerometer swinging through a fold, with jitter."""
    return (i % 3, 12000 - i * 400, 11000 + (i % 5))


class FreezeDetectorTest(unittest.TestCase):
    def run_samples(self, detector, base, count=40, step=2.0):
        frozen = set()
        for i in range(count):
            frozen = detector.update(i * step, {"lid": lid(i), "base": base(i)})
        return frozen

    def test_stuck_base_while_lid_moves(self):
        self.assertEqual(self.run_samples(sensors.FreezeDetector(), lambda i: STUCK), {"base"})

    def test_live_base_is_fine(self):
        detector = sensors.FreezeDetector()
        self.assertEqual(self.run_samples(detector, lambda i: (-223 + i % 4, -450, 8390)), set())

    def test_both_still_is_not_a_freeze(self):
        detector = sensors.FreezeDetector()
        frozen = set()
        for i in range(40):  # device lying on a table: both nearly constant
            frozen = detector.update(i * 2.0, {"lid": (0, 12000 + i % 2, 11000), "base": STUCK})
        self.assertEqual(frozen, set())

    def test_needs_the_full_hold_time(self):
        self.assertEqual(self.run_samples(sensors.FreezeDetector(hold=60), lambda i: STUCK, count=20), set())

    def test_clears_when_it_moves_again(self):
        detector = sensors.FreezeDetector()
        self.run_samples(detector, lambda i: STUCK)
        self.assertEqual(detector.update(100.0, {"lid": lid(50), "base": (-100, 9000, 3000)}), set())

    def test_unreadable_sensor_is_ignored(self):
        detector = sensors.FreezeDetector()
        frozen = set()
        for i in range(40):
            frozen = detector.update(i * 2.0, {"lid": lid(i), "base": None})
        self.assertEqual(frozen, set())


class AccelerometersTest(unittest.TestCase):
    def test_finds_cros_ec_accelerometers(self):
        with tempfile.TemporaryDirectory() as root:
            def device(n, name, location=None, xyz=None):
                path = os.path.join(root, f"iio:device{n}")
                os.makedirs(path)
                with open(os.path.join(path, "name"), "w") as fh:
                    fh.write(name + "\n")
                if location:
                    with open(os.path.join(path, "location"), "w") as fh:
                        fh.write(location + "\n")
                for axis, value in zip("xyz", xyz or ()):
                    with open(os.path.join(path, f"in_accel_{axis}_raw"), "w") as fh:
                        fh.write(f"{value}\n")
                return path
            lid_path = device(0, "cros-ec-accel", xyz=(1, 2, 3))
            device(1, "cros-ec-lid-angle")
            device(2, "cros-ec-accel", location="base", xyz=STUCK)
            found = sensors.accelerometers(root)
            self.assertEqual(sorted(found), ["base (iio:device2)", "iio:device0"])
            self.assertEqual(sensors.read_accel(lid_path), (1, 2, 3))
            self.assertEqual(sensors.read_accel(found["base (iio:device2)"]), STUCK)
            self.assertIsNone(sensors.read_accel(os.path.join(root, "iio:device1")))
