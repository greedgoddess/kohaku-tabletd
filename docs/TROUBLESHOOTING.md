# Troubleshooting

## Tablet mode is only detected in odd positions (Chromebooks)

**Symptom:** folding into tablet mode is not recognised, or only in some
positions (e.g. tent or stand, or only when the screen faces a certain way),
while the keyboard is still switched off as usual.

**Cause:** the Chromebook's embedded controller (EC) computes the hinge angle
from two accelerometers, one in the lid and one in the keyboard base. If the
base sensor gets stuck, the EC keeps reporting its last value, judges the fold
from the lid alone, and its tablet-mode switch flips at the wrong times.
kohaku-tabletd only reads that switch, so it follows the wrong decision.

kohaku-tabletd notices this: when one accelerometer stays identical to the
digit for a minute while the other one moves, it shows a notification and a
warning under **Scaling → Current state** in the settings window.

**Check it yourself:** run this and tilt the whole device, base included,
while it runs. Each line is one accelerometer reading per device.

```sh
for i in $(seq 12); do
  for d in /sys/bus/iio/devices/iio:device*; do
    [ "$(cat "$d/name")" = cros-ec-accel ] &&
      printf '%s: %s   ' "${d##*/}" "$(cat "$d"/in_accel_{x,y,z}_raw | tr '\n' ' ')"
  done
  echo; sleep 0.5
done
```

A working sensor changes on every line, even when the device lies still.
A sensor that repeats exactly the same three numbers is stuck. Setting its
sampling frequency does not help, since the EC itself has no fresh data.

**Fix: reset the EC.** It keeps running through normal reboots and
shutdowns, so it needs its own reset:

1. Shut down normally.
2. Hold **Refresh** (⟳, top row) and press **Power**. Release both once the
   device starts.

   Do **not** hold Esc as well: Esc + Refresh + Power starts Chromebook
   recovery mode.
3. Log in and run the check again; both sensors should change now.

If the base sensor stays frozen after an EC reset, the accelerometer or its
connection is probably faulty, and no software setting on the Linux side
can bring it back.
