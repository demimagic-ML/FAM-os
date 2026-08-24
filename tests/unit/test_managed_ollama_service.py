import stat
import tempfile
import unittest
from pathlib import Path

from fam_os.product.composition.managed_ollama import (
    ManagedOllamaService,
    ManagedOllamaSettings,
)
from fam_os.supervisor import ServiceRestartMode, ServiceState, ServiceStatus


class ManagedOllamaServiceTests(unittest.TestCase):
    def test_start_uses_dedicated_loopback_models_and_owned_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            model_root = Path(temporary) / "models"
            lifecycle = _Lifecycle(ServiceState.INACTIVE)
            service = ManagedOllamaService(
                _settings(model_root), lifecycle, _Health(True), _Identity(True),
            )
            status = service.start()
            self.assertEqual(ServiceState.ACTIVE, status.state)
            definition = lifecycle.started[0]
            self.assertEqual("fam-ollama", definition.service_id)
            self.assertIn(("OLLAMA_HOST", "127.0.0.1:11435"), definition.environment)
            self.assertIn(("OLLAMA_MODELS", str(model_root)), definition.environment)
            self.assertIs(
                ServiceRestartMode.ON_FAILURE, definition.restart_policy.mode,
            )
            self.assertEqual(0o700, stat.S_IMODE(model_root.stat().st_mode))

    def test_definition_includes_profile_accelerator_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = ManagedOllamaSettings(
                Path("/opt/ollama"), Path(temporary) / "models",
                accelerator_environment=(("CUDA_VISIBLE_DEVICES", "-1"),),
            )

            definition = settings.definition()

            self.assertIn(("CUDA_VISIBLE_DEVICES", "-1"), definition.environment)

    def test_unhealthy_start_stops_owned_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = _Lifecycle(ServiceState.INACTIVE)
            settings = ManagedOllamaSettings(
                Path("/opt/ollama"), Path(temporary) / "models",
                startup_timeout_seconds=0.01, poll_interval_seconds=0.001,
            )
            service = ManagedOllamaService(
                settings, lifecycle, _Health(False), _Identity(True),
            )
            with self.assertRaisesRegex(RuntimeError, "healthy"):
                service.start()
            self.assertEqual(["fam-ollama"], lifecycle.stopped)

    def test_reconcile_retains_only_active_healthy_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = _Lifecycle(ServiceState.ACTIVE)
            service = ManagedOllamaService(
                _settings(Path(temporary) / "models"), lifecycle, _Health(True),
                _Identity(True),
            )
            service.reconcile()
            self.assertEqual([], lifecycle.started)
            self.assertEqual([], lifecycle.stopped)

    def test_reconcile_replaces_healthy_service_with_wrong_process_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lifecycle = _Lifecycle(ServiceState.ACTIVE)
            service = ManagedOllamaService(
                _settings(Path(temporary) / "models"), lifecycle, _Health(True),
                _Identity(False),
            )
            service.reconcile()
            self.assertEqual(["fam-ollama"], lifecycle.stopped)
            self.assertEqual(1, len(lifecycle.started))


class _Lifecycle:
    def __init__(self, state) -> None:
        self.state = state
        self.started = []
        self.stopped = []

    def status(self, service_id):
        return ServiceStatus(service_id, self.state)

    def start(self, definition):
        self.started.append(definition)
        self.state = ServiceState.ACTIVE
        return ServiceStatus(definition.service_id, self.state, main_pid=123)

    def stop(self, service_id):
        self.stopped.append(service_id)
        self.state = ServiceState.INACTIVE
        return ServiceStatus(service_id, self.state)


class _Health:
    def __init__(self, ready) -> None:
        self._ready = ready

    def ready(self, _base_url):
        return self._ready


class _Identity:
    def __init__(self, matches) -> None:
        self._matches = matches

    def matches(self, _status, _definition):
        return self._matches


def _settings(model_root: Path) -> ManagedOllamaSettings:
    return ManagedOllamaSettings(Path("/opt/ollama"), model_root)


if __name__ == "__main__":
    unittest.main()
