import sys
import unittest

from fam_os.adapters.bubblewrap.process import SubprocessProcessLauncher
from fam_os.verification import IsolationLevel, SandboxLimits, SandboxStatus


class SandboxProcessCaptureTests(unittest.TestCase):
    def test_streams_and_caps_unbounded_child_output(self) -> None:
        script = "import sys\nfor _ in range(20000): sys.stdout.write('x' * 1024)"
        result = SubprocessProcessLauncher().run(
            (sys.executable, "-I", "-S", "-c", script),
            SandboxLimits(output_bytes=257), (), IsolationLevel.PROCESS_LIMITS,
        )
        self.assertEqual(SandboxStatus.COMPLETED, result.status)
        self.assertEqual(257, len(result.stdout))

    def test_timeout_kills_the_process_group(self) -> None:
        result = SubprocessProcessLauncher().run(
            (sys.executable, "-I", "-S", "-c", "while True: pass"),
            SandboxLimits(wall_seconds=0.05, cpu_seconds=2), (),
            IsolationLevel.PROCESS_LIMITS,
        )
        self.assertEqual(SandboxStatus.TIMED_OUT, result.status)
        self.assertLess(result.wall_seconds, 1.0)


if __name__ == "__main__":
    unittest.main()
