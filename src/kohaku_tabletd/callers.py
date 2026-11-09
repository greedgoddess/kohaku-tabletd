"""Who called the trigger API: the caller's process chain in /proc, with the
systemd unit (cgroup) as fallback for detached callers like keyd's commands."""

import os
import re

SHELLS = {"sh", "bash", "dash", "zsh", "fish"}
INTERPRETERS = ("python", "perl", "node", "ruby")
OWN = ("kohaku-tabletd", "kohaku_tabletd")
PASS_THROUGH = {"systemd", "systemd-run"}  # launchers, never the real source


# [doc:call-proc]
def read_process(pid, proc="/proc"):
    """(ppid, argv) of a process, or None if it is gone."""
    try:
        with open(f"{proc}/{pid}/stat") as fh:
            stat = fh.read()
        with open(f"{proc}/{pid}/cmdline", "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    ppid = int(stat[stat.rindex(")") + 2:].split()[1])
    argv = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
    if not argv:
        argv = [stat[stat.index("(") + 1:stat.rindex(")")]]
    return ppid, argv


# [doc:call-name]
def process_name(argv):
    """Readable name: the program, or the script an interpreter/shell runs."""
    base = os.path.basename(argv[0]).lstrip("-")
    if base.startswith(INTERPRETERS) or base in SHELLS:
        args = argv[1:]
        if args[:1] == ["-m"] and len(args) > 1:
            return args[1]
        if args and not args[0].startswith("-"):
            return os.path.basename(args[0])
    return base


def _is_wrapper(argv):
    return os.path.basename(argv[0]).lstrip("-") in SHELLS and argv[1:2] == ["-c"]


# [doc:call-unit]
def read_unit(pid, proc="/proc"):
    """Last component of the process's cgroup v2 path, e.g. "keyd.service"."""
    try:
        with open(f"{proc}/{pid}/cgroup") as fh:
            for line in fh:
                if line.startswith("0::"):
                    return line.strip()[3:].rstrip("/").rsplit("/", 1)[-1] or None
    except OSError:
        pass
    return None


def unit_source(unit):
    """Source name from a unit: "keyd.service" -> "keyd",
    "app-gnome-org.gnome.Ptyxis-4242.scope" -> "org.gnome.Ptyxis"."""
    name = unit.replace("\\x2d", "-")
    name = re.sub(r"\.(service|scope|slice)$", "", name)
    name = re.sub(r"@[^@]*$", "", name)
    if name.startswith("app-"):
        name = re.sub(r"^app-(gnome-|flatpak-|kde-)?", "", name)
        name = re.sub(r"-\d+$", "", name)
    return name or unit


# [doc:call-identify]
def identify(pid, proc="/proc", max_depth=12):
    """(source, chain). source is the first ancestor that is not our own CLI,
    a `sh -c` wrapper or a launcher. If the chain ends without one (the caller
    was detached, e.g. by keyd), the caller's systemd unit names the source."""
    chain = []
    current = pid
    while current > 1 and len(chain) < max_depth:
        info = read_process(current, proc)
        if info is None:
            break
        ppid, argv = info
        name = process_name(argv)
        chain.append(name)
        skip = any(own in name for own in OWN) or _is_wrapper(argv) or name in PASS_THROUGH
        if not skip:
            return name, " › ".join(reversed(chain))
        current = ppid
    unit = read_unit(pid, proc)
    if unit:
        return unit_source(unit), " › ".join([unit] + list(reversed(chain)))
    return (chain[-1] if chain else "unknown"), " › ".join(reversed(chain))
