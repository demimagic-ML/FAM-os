import unittest

from fam_os.adapters.bubblewrap.runner import BubblewrapSandboxRunner
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.verification import (
    IsolationLevel,
    SandboxRequest,
    SandboxResult,
    SandboxStatus,
)


class FakeLocator:
    def __init__(self, paths):
        self.paths = paths

    def find(self, executable):
        return self.paths.get(executable)


class FakeLauncher:
    def __init__(self):
        self.calls = []

    def run(self, command, limits, environment, isolation):
        self.calls.append((command, limits, environment, isolation))
        return SandboxResult(SandboxStatus.COMPLETED, isolation, 0.1, exit_code=0)


class FailingBubblewrapLauncher(FakeLauncher):
    def run(self, command, limits, environment, isolation):
        return SandboxResult(
            SandboxStatus.COMPLETED, isolation, 0.1,
            stderr="bwrap: Creating new namespace failed", exit_code=1,
        )


class BubblewrapRunnerTests(unittest.TestCase):
    def test_refuses_silent_isolation_downgrade(self) -> None:
        launcher = FakeLauncher()
        runner = BubblewrapSandboxRunner(
            locator=FakeLocator({"python3": "/usr/bin/python3"}), launcher=launcher
        )
        result = runner.run(SandboxRequest("pass"))
        self.assertEqual(result.status, SandboxStatus.UNAVAILABLE)
        self.assertEqual(result.isolation, IsolationLevel.NONE)
        self.assertEqual(launcher.calls, [])

    def test_reports_explicit_process_limit_fallback(self) -> None:
        launcher = FakeLauncher()
        settings = BubblewrapSettings(require_bubblewrap=False)
        runner = BubblewrapSandboxRunner(
            settings, FakeLocator({"python3": "/usr/bin/python3"}), launcher
        )
        result = runner.run(SandboxRequest("pass"))
        self.assertEqual(result.isolation, IsolationLevel.PROCESS_LIMITS)
        self.assertEqual(launcher.calls[0][0][0], "/usr/bin/python3")

    def test_uses_bubblewrap_when_available(self) -> None:
        launcher = FakeLauncher()
        locator = FakeLocator({"python3": "/usr/bin/python3", "bwrap": "/usr/bin/bwrap", "systemd-run": "/usr/bin/systemd-run"})
        runner = BubblewrapSandboxRunner(locator=locator, launcher=launcher)
        result = runner.run(SandboxRequest("pass"))
        self.assertEqual(result.isolation, IsolationLevel.BUBBLEWRAP)
        self.assertEqual(launcher.calls[0][0][0], "/usr/bin/systemd-run")
        self.assertIn("TasksMax=16", launcher.calls[0][0])

    def test_namespace_setup_failure_is_unavailable_not_candidate_failure(self) -> None:
        locator = FakeLocator({"python3": "/usr/bin/python3", "bwrap": "/usr/bin/bwrap", "systemd-run": "/usr/bin/systemd-run"})
        result = BubblewrapSandboxRunner(
            locator=locator, launcher=FailingBubblewrapLauncher()
        ).run(SandboxRequest("pass"))
        self.assertEqual(SandboxStatus.UNAVAILABLE, result.status)
        self.assertEqual(IsolationLevel.NONE, result.isolation)


if __name__ == "__main__":
    unittest.main()
