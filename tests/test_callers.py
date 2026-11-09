import os
import tempfile
import unittest

from kohaku_tabletd import callers


class CallersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proc = self.tmp.name

    def add(self, pid, ppid, *argv, comm=None):
        path = os.path.join(self.proc, str(pid))
        os.makedirs(path)
        with open(os.path.join(path, "stat"), "w") as fh:
            fh.write(f"{pid} ({comm or os.path.basename(argv[0] if argv else 'kthread')}) S {ppid} 1 1 0\n")
        with open(os.path.join(path, "cmdline"), "wb") as fh:
            fh.write(b"".join(a.encode() + b"\0" for a in argv))

    def test_keyd_through_shell_and_cli(self):
        self.add(100, 1, "/usr/bin/keyd")
        self.add(200, 100, "sh", "-c", "/usr/bin/kohaku-tabletd --active-user toggle")
        self.add(300, 200, "/usr/bin/python3", "/usr/bin/kohaku-tabletd", "--active-user", "toggle")
        self.assertEqual(callers.identify(300, self.proc), ("keyd", "keyd › sh › kohaku-tabletd"))

    def test_script_run_by_interpreter_is_the_source(self):
        self.add(50, 1, "-bash")
        self.add(60, 50, "/usr/bin/python3", "/home/user/bin/flip.py")
        self.assertEqual(callers.identify(60, self.proc), ("flip.py", "flip.py"))

    def test_terminal_shell_is_the_source(self):
        self.add(50, 1, "-bash")
        self.add(70, 50, "/usr/bin/python3", "/usr/bin/kohaku-tabletd", "toggle")
        self.assertEqual(callers.identify(70, self.proc), ("bash", "bash › kohaku-tabletd"))

    def test_process_names(self):
        self.assertEqual(callers.process_name(["python3", "-m", "kohaku_tabletd"]), "kohaku_tabletd")
        self.assertEqual(callers.process_name(["/usr/lib/systemd/systemd", "--user"]), "systemd")

    def test_vanished_process(self):
        self.assertEqual(callers.identify(999, self.proc), ("unknown", ""))
