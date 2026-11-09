import os
import tempfile
import unittest

from kohaku_tabletd import switch


def event(etype, code, value=1):
    return switch.INPUT_EVENT.pack(0, 0, etype, code, value)


class SwitchTest(unittest.TestCase):
    def test_find_device_by_capability(self):
        with tempfile.TemporaryDirectory() as root:
            for name, bits in (("event3", "1"), ("event7", "2"), ("event9", "0")):
                caps = os.path.join(root, name, "device", "capabilities")
                os.makedirs(caps)
                with open(os.path.join(caps, "sw"), "w") as fh:
                    fh.write(bits + "\n")
            self.assertEqual(switch.find_device(root), "/dev/input/event7")

    def test_find_device_prefers_named_switch(self):
        with tempfile.TemporaryDirectory() as root:
            for name, label in (("event2", "Intel Virtual Switches"), ("event6", "Tablet Mode Switch")):
                dev = os.path.join(root, name, "device")
                os.makedirs(os.path.join(dev, "capabilities"))
                with open(os.path.join(dev, "capabilities", "sw"), "w") as fh:
                    fh.write("2\n")
                with open(os.path.join(dev, "name"), "w") as fh:
                    fh.write(label + "\n")
            self.assertEqual(switch.find_device(root), "/dev/input/event6")

    def test_drain(self):
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        sw = switch.TabletSwitch()
        sw.fd = read_fd
        self.addCleanup(sw.close)
        os.write(write_fd, event(0x01, 30) + event(0x00, 0))
        self.assertFalse(sw.drain())
        os.write(write_fd, event(switch.EV_SW, switch.SW_TABLET_MODE) + event(0x00, 0))
        self.assertTrue(sw.drain())
        os.close(write_fd)
        with self.assertRaises(OSError):
            sw.drain()
