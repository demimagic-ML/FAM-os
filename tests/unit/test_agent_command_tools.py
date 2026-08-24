import tempfile
import unittest
from pathlib import Path

from fam_os.core.agent import AgentAuthorityProfile, AgentToolCall, AgentToolRegistry
from fam_os.product.agent_command_tools import WorkspaceCommandTools
from fam_os.verification.sandbox import IsolationLevel, SandboxResult, SandboxStatus


class _Locator:
    def find(self, executable):
        return "/usr/bin/bwrap" if executable == "bwrap" else None


class _Launcher:
    def __init__(self):
        self.calls = []

    def run(self, command, limits, environment, isolation):
        self.calls.append((command, limits, environment, isolation))
        return SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP,
            0.1, "tests passed\n", "", 0,
        )


class AgentCommandToolsTests(unittest.TestCase):
    def test_workspace_command_is_bound_without_network_and_returns_real_status(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = _Launcher()
            registry = AgentToolRegistry()
            WorkspaceCommandTools(
                Path(directory), locator=_Locator(), launcher=launcher,
            ).register(registry)

            result = registry.invoke(AgentToolCall(
                "call", "run_command",
                {"command": ["python3", "-m", "unittest"], "timeout_seconds": 30},
                "Run the tests.",
            ), AgentAuthorityProfile.WORKSPACE)

            self.assertTrue(result.succeeded)
            self.assertIn("exit_code=0", result.output)
            command, limits, _environment, isolation = launcher.calls[0]
            root = str(Path(directory).resolve())
            self.assertIn("--unshare-all", command)
            self.assertEqual(root, command[command.index("--bind") + 1])
            self.assertEqual(root, command[command.index("--chdir") + 1])
            self.assertEqual(("python3", "-m", "unittest"), command[-3:])
            self.assertEqual(30, limits.wall_seconds)
            self.assertEqual(IsolationLevel.BUBBLEWRAP, isolation)

    def test_ask_profile_does_not_launch_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = _Launcher()
            registry = AgentToolRegistry()
            WorkspaceCommandTools(
                Path(directory), locator=_Locator(), launcher=launcher,
            ).register(registry)
            result = registry.invoke(AgentToolCall(
                "call", "run_command", {"command": ["true"]}, "Run it.",
            ), AgentAuthorityProfile.ASK)

            self.assertFalse(result.succeeded)
            self.assertEqual([], launcher.calls)


if __name__ == "__main__":
    unittest.main()
