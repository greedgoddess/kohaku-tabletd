"""Mode state machine: the hinge decides, unless the user overrode it."""

LAPTOP = "laptop"
TABLET = "tablet"
MODES = (LAPTOP, TABLET)


# [doc:st-model]
class ModeState:
    def __init__(self, physical=LAPTOP):
        self.physical = physical
        self.override = None

    @property
    def effective(self):
        return self.override or self.physical

    @property
    def manual(self):
        return self.override is not None

    # [doc:st-hinge]
    def hinge(self, physical):
        """Record a hinge reading. Only a real transition counts, and it
        drops any manual override. Returns True on a transition."""
        if physical not in MODES:
            raise ValueError(f"unknown mode {physical!r}")
        if physical == self.physical:
            return False
        self.physical = physical
        self.override = None
        return True

    # [doc:st-manual]
    def set(self, mode):
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r} (expected laptop or tablet)")
        self.override = mode

    def toggle(self):
        self.set(TABLET if self.effective == LAPTOP else LAPTOP)

    def auto(self):
        self.override = None
