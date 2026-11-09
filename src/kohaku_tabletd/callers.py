"""Who called the trigger API: walk the caller's process chain in /proc."""

import os

SHELLS = {"sh", "bash", "dash", "zsh", "fish"}
INTERPRETERS = ("python", "perl", "node", "ruby")
OWN = ("kohaku-tabletd", "kohaku_tabletd")


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


# [doc:call-identify]
def identify(pid, proc="/proc", max_depth=12):
    """(source, chain). source is the first ancestor that is neither our own
    CLI nor a `sh -c` wrapper; chain reads from the source down to the caller."""
    chain = []
    while pid > 1 and len(chain) < max_depth:
        info = read_process(pid, proc)
        if info is None:
            break
        ppid, argv = info
        name = process_name(argv)
        chain.append(name)
        if not any(own in name for own in OWN) and not _is_wrapper(argv):
            return name, " › ".join(reversed(chain))
        pid = ppid
    return (chain[-1] if chain else "unknown"), " › ".join(reversed(chain))
