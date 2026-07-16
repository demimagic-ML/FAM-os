"""Opt-in live checks for the Phase 1 Bubblewrap sandbox mechanics."""

import os
import unittest

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.verification import (
    IsolationLevel,
    SandboxLimits,
    SandboxRequest,
    SandboxStatus,
)


@unittest.skipUnless(os.getenv("FAM_SANDBOX_SMOKE") == "1", "live sandbox smoke disabled")
class PythonSandboxSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = BubblewrapSandboxRunner()

    def require_live_isolation(self, result) -> None:
        if result.status is SandboxStatus.UNAVAILABLE:
            self.skipTest(result.reason)

    def test_hides_user_home_from_sandbox_root(self) -> None:
        script = "from pathlib import Path\nassert not Path('/home').exists()\n"
        result = self.runner.run(SandboxRequest(script))
        self.require_live_isolation(result)
        self.assertEqual(result.status, SandboxStatus.COMPLETED, result.stderr)
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(result.isolation, IsolationLevel.BUBBLEWRAP)

    def test_enforces_wall_timeout(self) -> None:
        limits = SandboxLimits(wall_seconds=0.1, cpu_seconds=1)
        result = self.runner.run(SandboxRequest("while True: pass", limits))
        self.require_live_isolation(result)
        self.assertEqual(result.status, SandboxStatus.TIMED_OUT)

    def test_bounds_returned_output(self) -> None:
        limits = SandboxLimits(output_bytes=128)
        result = self.runner.run(SandboxRequest("print('x' * 10000)", limits))
        self.require_live_isolation(result)
        self.assertEqual(result.status, SandboxStatus.COMPLETED)
        self.assertEqual(len(result.stdout), 128)


if __name__ == "__main__":
    unittest.main()
