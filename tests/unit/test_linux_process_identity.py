import os
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.process_identity import LinuxProcessIdentity
from fam_os.supervisor import (
    ResourceLimits,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
)


class LinuxProcessIdentityTests(unittest.TestCase):
    def test_matches_exact_executable_arguments_and_required_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "ollama"
            executable.write_bytes(b"binary")
            process = root / "proc/41"
            process.mkdir(parents=True)
            (process / "exe").symlink_to(executable)
            (process / "cmdline").write_bytes(
                os.fsencode(str(executable)) + b"\0serve\0"
            )
            (process / "environ").write_bytes(
                b"IGNORED=value\0OLLAMA_HOST=127.0.0.1:11435\0"
                + b"OLLAMA_MODELS=/owned/models\0"
            )
            definition = ServiceDefinition(
                "fam-ollama", (str(executable), "serve"),
                (
                    ("OLLAMA_HOST", "127.0.0.1:11435"),
                    ("OLLAMA_MODELS", "/owned/models"),
                ),
                ResourceLimits(),
            )
            status = ServiceStatus(
                "fam-ollama", ServiceState.ACTIVE, main_pid=41,
            )
            identity = LinuxProcessIdentity(root / "proc")
            self.assertTrue(identity.matches(status, definition))

            wrong_root = ServiceDefinition(
                "fam-ollama", definition.command,
                (
                    ("OLLAMA_HOST", "127.0.0.1:11435"),
                    ("OLLAMA_MODELS", "/different/models"),
                ),
                ResourceLimits(),
            )
            self.assertFalse(identity.matches(status, wrong_root))

    def test_missing_pid_or_unreadable_procfs_fails_closed(self) -> None:
        definition = ServiceDefinition(
            "fam-ollama", ("/opt/ollama", "serve"), (), ResourceLimits(),
        )
        identity = LinuxProcessIdentity(Path("/absent/proc"))
        self.assertFalse(identity.matches(
            ServiceStatus("fam-ollama", ServiceState.ACTIVE), definition,
        ))
        self.assertFalse(identity.matches(
            ServiceStatus("fam-ollama", ServiceState.ACTIVE, main_pid=99),
            definition,
        ))


if __name__ == "__main__":
    unittest.main()
