"""Spot a frozen hinge sensor on Chromebooks.

The embedded controller computes the hinge angle (and so the tablet-mode
switch) from two accelerometers, lid and base. If one stops updating, the
controller keeps handing out its last value and tablet mode is detected only
in odd positions. A live accelerometer always jitters, so a reading that stays
identical to the digit while the other sensor moves means it is stuck."""

import collections
import glob
import os

CROS_EC_ACCEL = "cros-ec-accel"
AXES = ("x", "y", "z")


# [doc:sns-find]
def accelerometers(root="/sys/bus/iio/devices"):
    """{label: device dir} of the Chromebook EC's accelerometers."""
    found = {}
    for device in sorted(glob.glob(os.path.join(root, "iio:device*"))):
        try:
            with open(os.path.join(device, "name")) as fh:
                name = fh.read().strip()
        except OSError:
            continue
        if name != CROS_EC_ACCEL:
            continue
        label = os.path.basename(device)
        try:
            with open(os.path.join(device, "location")) as fh:
                label = f"{fh.read().strip()} ({label})"
        except OSError:
            pass
        found[label] = device
    return found


def read_accel(device):
    """(x, y, z) raw reading, or None if it can't be read."""
    try:
        values = []
        for axis in AXES:
            with open(os.path.join(device, f"in_accel_{axis}_raw")) as fh:
                values.append(int(fh.read().strip()))
        return tuple(values)
    except (OSError, ValueError):
        return None


# [doc:sns-freeze]
class FreezeDetector:
    """Feed readings over time; reports sensors that stayed identical for
    `hold` seconds while another sensor moved by at least `movement` (raw
    units) in that time. Stays reported until the sensor changes again."""

    def __init__(self, hold=60.0, movement=2000):
        self.hold = hold
        self.movement = movement
        self.last = {}
        self.since = {}
        self.history = collections.defaultdict(collections.deque)
        self.frozen = set()

    def _moved(self, label):
        samples = [value for _t, value in self.history[label]]
        if len(samples) < 2:
            return 0
        return max(max(axis) - min(axis) for axis in zip(*samples))

    def update(self, now, readings):
        for label, value in readings.items():
            if value is None:
                continue
            if value != self.last.get(label):
                self.last[label], self.since[label] = value, now
                self.frozen.discard(label)
            history = self.history[label]
            history.append((now, value))
            while history and history[0][0] < now - self.hold:
                history.popleft()
        for label in self.last:
            if label in self.frozen or now - self.since[label] < self.hold:
                continue
            if any(self._moved(other) >= self.movement for other in self.last if other != label):
                self.frozen.add(label)
        return set(self.frozen)
