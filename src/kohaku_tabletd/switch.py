"""Read the kernel's tablet-mode switch (SW_TABLET_MODE) straight from evdev."""

import array
import fcntl
import glob
import os
import struct

EV_SW = 0x05
SW_TABLET_MODE = 0x01
SW_MAX = 0x10
INPUT_EVENT = struct.Struct("llHHi")  # struct input_event with 64-bit time


# [doc:sw-find]
def find_device(sysfs="/sys/class/input", preferred="Tablet Mode Switch"):
    """Evdev node whose switch capabilities include SW_TABLET_MODE. If several
    do, the one named `preferred` (the Chromebook EC switch) wins."""
    candidates = []
    pattern = os.path.join(sysfs, "event*", "device", "capabilities", "sw")
    for cap in sorted(glob.glob(pattern)):
        try:
            with open(cap) as fh:
                words = fh.read().split()
        except OSError:
            continue
        if not (words and int(words[-1], 16) & (1 << SW_TABLET_MODE)):
            continue
        device_dir = os.path.dirname(os.path.dirname(cap))
        try:
            with open(os.path.join(device_dir, "name")) as fh:
                name = fh.read().strip()
        except OSError:
            name = ""
        path = "/dev/input/" + os.path.basename(os.path.dirname(device_dir))
        if name == preferred:
            return path
        candidates.append(path)
    return candidates[0] if candidates else None


def _eviocgsw(length):
    return (2 << 30) | (length << 16) | (ord("E") << 8) | 0x1B


# [doc:sw-read]
def read_tablet_mode(fd):
    """Current switch state via EVIOCGSW, independent of queued events."""
    buf = array.array("B", bytes(SW_MAX // 8 + 1))
    fcntl.ioctl(fd, _eviocgsw(len(buf)), buf, True)
    return bool(buf[SW_TABLET_MODE // 8] & (1 << (SW_TABLET_MODE % 8)))


class TabletSwitch:
    def __init__(self, path=""):
        self.path = path
        self.path_in_use = None
        self.fd = None

    # [doc:sw-open]
    def open(self):
        path = self.path or find_device()
        if not path:
            return False
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        self.path_in_use = path
        return True

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.fd = None
        self.path_in_use = None

    def tablet(self):
        return read_tablet_mode(self.fd)

    # [doc:sw-drain]
    def drain(self):
        """Consume pending events. True if the tablet switch reported anything.
        Raises OSError when the device went away."""
        moved = False
        while True:
            try:
                data = os.read(self.fd, INPUT_EVENT.size * 32)
            except BlockingIOError:
                return moved
            if not data:
                raise OSError("tablet switch device closed")
            usable = len(data) - len(data) % INPUT_EVENT.size
            for offset in range(0, usable, INPUT_EVENT.size):
                _sec, _usec, etype, code, _value = INPUT_EVENT.unpack_from(data, offset)
                if etype == EV_SW and code == SW_TABLET_MODE:
                    moved = True
