import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.bubblewrap import (
    BubblewrapAccessResource,
    BubblewrapServiceAccessAdapter,
)
from fam_os.adapters.cgroup.paths import CgroupV2Paths
from fam_os.adapters.systemd.commands import build_start_command
from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.supervisor import (
    AccessMode,
    AccessResourceKind,
    InMemoryServiceOwnershipRegistry,
    OwnedService,
    ServiceAccessGrant,
    ServiceDefinition,
    ServiceOwnershipError,
    SupervisorCallContext,
    SupervisorNonGoal,
    canonical_supervisor_boundary,
)


ROOT = Path(__file__).parents[2]
FORBIDDEN_IMPORTS = (
    "fam_os.core", "fam_os.routing", "fam_os.experts", "fam_os.memory",
    "fam_os.application",
)
NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


class SupervisorThreatTests(unittest.TestCase):
    def test_transport_identity_control_characters_are_rejected(self):
        values = ("principal\nforged", " authority", "x" * 257)
        for value in values:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    SupervisorCallContext("request-1", value, "session-1", "auth-1")

    def test_service_definition_rejects_control_and_resource_exhaustion(self):
        invalid = (
            ServiceDefinition.__name__,
            ("/usr/bin/true\n--property=User=root",),
            ("x" * 4097,),
            tuple("x" for _ in range(257)),
        )
        for command in invalid[1:]:
            with self.subTest(size=len(command)):
                with self.assertRaises(ValueError):
                    ServiceDefinition("fam-threat", command)
        with self.assertRaises(ValueError):
            ServiceDefinition("fam-threat", ("/usr/bin/true",), (("MODE", "x\r"),))

    def test_systemd_and_bubblewrap_commands_have_option_terminators(self):
        definition = ServiceDefinition("fam-threat", ("--property=User=root",))
        systemd = build_start_command(definition, SystemdUserSettings())
        self.assertEqual(("--", "--property=User=root"), systemd[-2:])

        access = BubblewrapServiceAccessAdapter((BubblewrapAccessResource(
            "filesystem.safe", AccessResourceKind.FILESYSTEM,
            Path("/trusted/source"), Path("/access/source"),
        ),))
        projected = access.project(definition)
        self.assertEqual(("--", "--property=User=root"), projected.command[-2:])

    def test_systemd_commands_are_user_scoped_and_unit_identity_is_bounded(self):
        command = build_start_command(
            ServiceDefinition("fam-threat", ("/usr/bin/true",)),
            SystemdUserSettings(),
        )
        self.assertIn("--user", command)
        self.assertNotIn("--system", command)
        with self.assertRaises(ValueError):
            ServiceDefinition("fam-" + "x" * 200, ("/usr/bin/true",))

    def test_arbitrary_system_unit_cannot_enter_ownership_registry(self):
        registry = InMemoryServiceOwnershipRegistry()
        service = OwnedService(
            "principal-1", "session-1",
            ServiceDefinition("ssh.service", ("/usr/bin/true",)),
        )
        with self.assertRaises(ServiceOwnershipError):
            registry.claim(service)
        self.assertIsNone(registry.get("ssh.service"))

    def test_grant_identity_and_resource_paths_reject_injection(self):
        with self.assertRaises(ValueError):
            ServiceAccessGrant(
                "grant\nforged", "auth-1", "principal-1", "session-1",
                "fam-threat", "filesystem.safe", AccessResourceKind.FILESYSTEM,
                AccessMode.READ, NOW, NOW + timedelta(minutes=1),
            )
        with self.assertRaises(ValueError):
            BubblewrapAccessResource(
                "filesystem.safe", AccessResourceKind.FILESYSTEM,
                Path("/trusted/source\nforged"), Path("/access/source"),
            )
        with self.assertRaises(ValueError):
            CgroupV2Paths().group("../../system.slice")

    def test_boundary_excludes_intelligence_and_system_administration(self):
        boundary = canonical_supervisor_boundary()
        self.assertFalse(boundary.system_service_control_allowed)
        self.assertFalse(boundary.model_logic_allowed)
        self.assertIn(SupervisorNonGoal.MODEL_INFERENCE, boundary.non_goals)
        self.assertIn(
            SupervisorNonGoal.SYSTEM_SERVICE_ADMINISTRATION, boundary.non_goals
        )

    def test_supervisor_source_has_no_intelligence_layer_imports(self):
        violations = []
        for path in (ROOT / "src/fam_os/supervisor").rglob("*.py"):
            violations.extend(_forbidden_imports(path))
        self.assertEqual([], violations)


def _forbidden_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []
    for node in ast.walk(tree):
        names = _imported_names(node)
        for name in names:
            if name.startswith(FORBIDDEN_IMPORTS):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")
    return violations


def _imported_names(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
