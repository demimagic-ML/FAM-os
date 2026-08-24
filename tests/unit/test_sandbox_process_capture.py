import resource
import sys
import unittest
from unittest.mock import call, patch

from fam_os.adapters.bubblewrap.process import SubprocessProcessLauncher
from fam_os.adapters.bubblewrap.rlimits import apply_resource_limits
from fam_os.verification import IsolationLevel, SandboxLimits, SandboxStatus


class SandboxProcessCaptureTests(unittest.TestCase):
    def test_streams_and_caps_unbounded_child_output(self) -> None:
        script = "import sys\nfor _ in range(20000): sys.stdout.write('x' * 1024)"
        result = SubprocessProcessLauncher().run(
            (sys.executable, "-I", "-S", "-c", script),
            SandboxLimits(output_bytes=257), (), IsolationLevel.PROCESS_LIMITS,
        )
        self.assertEqual(SandboxStatus.OUTPUT_LIMIT, result.status)
        self.assertEqual(257, len(result.stdout))
        self.assertIn("output bytes", result.reason)

    def test_timeout_kills_the_process_group(self) -> None:
        result = SubprocessProcessLauncher().run(
            (sys.executable, "-I", "-S", "-c", "while True: pass"),
            SandboxLimits(wall_seconds=0.05, cpu_seconds=2), (),
            IsolationLevel.PROCESS_LIMITS,
        )
        self.assertEqual(SandboxStatus.TIMED_OUT, result.status)
        self.assertLess(result.wall_seconds, 1.0)

    def test_cgroup_managed_launcher_does_not_apply_virtual_address_limit(self) -> None:
        limits = SandboxLimits(memory_bytes=512 * 1024**2)
        with patch("fam_os.adapters.bubblewrap.rlimits.resource.setrlimit") as setter:
            apply_resource_limits(limits, cgroup_memory_managed=True)
        self.assertNotIn(
            call(
                resource.RLIMIT_AS,
                (limits.memory_bytes, limits.memory_bytes),
            ),
            setter.call_args_list,
        )
        with patch("fam_os.adapters.bubblewrap.rlimits.resource.setrlimit") as setter:
            apply_resource_limits(limits)
        self.assertIn(
            call(
                resource.RLIMIT_AS,
                (limits.memory_bytes, limits.memory_bytes),
            ),
            setter.call_args_list,
        )


if __name__ == "__main__":
    unittest.main()
