import unittest
from pathlib import Path

from fam_os.adapters.systemd import SystemdUserServiceLifecycle, SystemdUserSettings
from fam_os.supervisor import ServiceDefinition, ServiceLifecycleError, ServiceState


FIXTURE = Path(__file__).parents[1] / "fixtures" / "systemd" / "show-active.txt"


class FakeRunner:
    def __init__(self, fail_start: bool = False) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.active = False
        self.fail_start = fail_start

    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None:
        self.commands.append(command)
        if command[0] == "systemd-run":
            if self.fail_start:
                return None
            self.active = True
            return "Running as unit fam-test.service."
        if "stop" in command:
            self.active = False
            return ""
        if "show" in command and self.active:
            return FIXTURE.read_text()
        if "show" in command:
            return "ActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\n"
        return None


class SystemdLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = FakeRunner()
        self.lifecycle = SystemdUserServiceLifecycle(self.runner, SystemdUserSettings())

    def test_starts_observes_and_stops_service(self) -> None:
        definition = ServiceDefinition("fam-test", ("/usr/bin/sleep", "30"))
        started = self.lifecycle.start(definition)
        self.assertEqual(started.state, ServiceState.ACTIVE)
        self.assertEqual(started.main_pid, 4242)
        self.assertTrue(started.resource_group.endswith("fam-test.service"))

        stopped = self.lifecycle.stop("fam-test")
        self.assertEqual(stopped.state, ServiceState.INACTIVE)
        self.assertIsNone(stopped.main_pid)

    def test_exposes_control_group_to_resource_adapter(self) -> None:
        self.lifecycle.start(ServiceDefinition("fam-test", ("/usr/bin/true",)))
        self.assertTrue(self.lifecycle.control_group("fam-test").startswith("/user.slice/"))

    def test_translates_start_failure(self) -> None:
        lifecycle = SystemdUserServiceLifecycle(FakeRunner(fail_start=True))
        with self.assertRaisesRegex(ServiceLifecycleError, "could not start"):
            lifecycle.start(ServiceDefinition("fam-test", ("/usr/bin/false",)))


if __name__ == "__main__":
    unittest.main()
