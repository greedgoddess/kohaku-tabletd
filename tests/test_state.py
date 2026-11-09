import unittest

from kohaku_tabletd.state import LAPTOP, TABLET, ModeState


class ModeStateTest(unittest.TestCase):
    def test_hinge_transition_drops_override(self):
        s = ModeState()
        s.toggle()
        self.assertEqual((s.effective, s.manual), (TABLET, True))
        self.assertTrue(s.hinge(TABLET))
        self.assertEqual((s.effective, s.manual), (TABLET, False))

    def test_repeated_hinge_reading_keeps_override(self):
        s = ModeState()
        s.set(TABLET)
        self.assertFalse(s.hinge(LAPTOP))
        self.assertEqual(s.effective, TABLET)

    def test_auto_follows_hinge(self):
        s = ModeState(physical=TABLET)
        s.set(LAPTOP)
        s.auto()
        self.assertEqual((s.effective, s.manual), (TABLET, False))

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            ModeState().set("desk")
