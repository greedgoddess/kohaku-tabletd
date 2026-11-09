"""kohaku-tabletd: tablet-mode aware display scaling with one D-Bus control point."""

__version__ = "0.2.0"

# [doc:pkg-bus-names]
BUS_NAME = "io.github.greedgoddess.KohakuTabletd"
OBJECT_PATH = "/io/github/greedgoddess/KohakuTabletd"
INTERFACE = BUS_NAME
SETTINGS_APP_ID = BUS_NAME + ".Settings"
HINGE_SOURCE = "hinge"  # source name recorded for hinge transitions (never blockable)
