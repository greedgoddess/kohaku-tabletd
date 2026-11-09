import datetime
import unittest

from kohaku_tabletd import fmt


class FmtTest(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(fmt.percent(2.0), "200 %")
        self.assertEqual(fmt.percent(2.6666667461395264), "266.67 %")
        self.assertEqual(fmt.percent(1.25), "125 %")

    def test_nearest_index(self):
        self.assertEqual(fmt.nearest_index([1.0, 2.0, 2.6666667, 3.0], 2.6667), 2)

    def test_remote_error(self):
        msg = "GDBus.Error:io.github.greedgoddess.KohakuTabletd.Error.Blocked: keyd is blocked"
        self.assertEqual(fmt.remote_error(msg), "keyd is blocked")
        self.assertEqual(fmt.remote_error("plain"), "plain")

    def test_when(self):
        now = datetime.datetime(2026, 11, 9, 15, 0)
        today = int(datetime.datetime(2026, 11, 9, 14, 5, 7).timestamp() * 1000)
        earlier = int(datetime.datetime(2026, 11, 8, 9, 30).timestamp() * 1000)
        self.assertEqual(fmt.when(today, now), "14:05:07")
        self.assertEqual(fmt.when(earlier, now), "Nov 08 09:30")
