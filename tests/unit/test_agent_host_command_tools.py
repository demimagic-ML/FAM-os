import tempfile
import unittest
from pathlib import Path

from fam_os.core.agent import AgentAuthorityProfile, AgentToolCall, AgentToolRegistry
from fam_os.product.agent_host_command_tools import HostCommandTools
from fam_os.verification.sandbox import IsolationLevel, SandboxResult, SandboxStatus


class _Launcher:
    def __init__(self):
        self.calls = []

    def run(self, command, limits, environment, isolation):
        self.calls.append((command, limits, environment, isolation))
        return SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.NONE, 0.1,
            "host check passed\n", "", 0,
        )


class HostCommandToolsTests(unittest.TestCase):
    def test_full_os_profile_runs_current_user_host_command_from_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = _Launcher()
            registry = AgentToolRegistry()
            HostCommandTools(Path(directory), launcher=launcher).register(registry)

            result = registry.invoke(AgentToolCall(
                "call", "run_host_command", {"command": ["git", "status"]},
                "Inspect the host repository.",
            ), AgentAuthorityProfile.FULL_OS)

            self.assertTrue(result.succeeded)
            command, _limits, environment, isolation = launcher.calls[0]
            self.assertEqual(
                ("/usr/bin/env", "--chdir", str(Path(directory).resolve()),
                 "git", "status"),
                command,
            )
            self.assertTrue(environment)
            self.assertEqual(IsolationLevel.NONE, isolation)

    def test_workspace_profile_cannot_launch_host_command(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = _Launcher()
            registry = AgentToolRegistry()
            HostCommandTools(Path(directory), launcher=launcher).register(registry)

            result = registry.invoke(AgentToolCall(
                "call", "run_host_command", {"command": ["true"]}, "Run it.",
            ), AgentAuthorityProfile.WORKSPACE)

            self.assertFalse(result.succeeded)
            self.assertEqual([], launcher.calls)


if __name__ == "__main__":
    unittest.main()
