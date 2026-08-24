import tempfile
import unittest
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from tools.phase23_installed_matrix.contracts import (
    REQUIRED_SCENARIOS,
    InstalledMatrixSettings,
)
from tools.phase23_installed_matrix.application_scenario import _inject_fault_window
from tools.phase23_installed_matrix.evidence import finalize
from tools.phase23_installed_matrix.escalation_scenario import _known_provider_models
from tools.phase23_installed_matrix.factory_process import _json_default
from tools.phase23_installed_matrix.factory_scenario import run_factory_scenario
from tools.phase23_installed_matrix.model_control import restrict_candidate_experts
from tools.phase23_installed_matrix.mcp_scenario import (
    _ingress_tool_name,
    _resource_capability_id,
    _tool_capability_id,
    _write_ingress_configuration,
    _write_outbound_configuration,
)
from tools.phase23_installed_matrix.service import CandidateService
from tools.phase23_installed_matrix.scenario import run_installed_matrix


class Phase23InstalledScenarioMatrixTests(unittest.TestCase):
    def test_matrix_uses_short_private_execution_root_for_unix_sockets(self):
        with tempfile.TemporaryDirectory() as raw:
            settings = Mock()
            settings.output_root = Path(raw) / "output"
            with patch(
                "tools.phase23_installed_matrix.scenario.tempfile.TemporaryDirectory",
                side_effect=RuntimeError("captured"),
            ) as temporary:
                with self.assertRaisesRegex(RuntimeError, "captured"):
                    run_installed_matrix(settings)
            self.assertEqual("f23i-", temporary.call_args.kwargs["prefix"])

    def test_mcp_qualification_configs_are_private_and_exactly_allowlisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            (repository / "tests/fixtures").mkdir(parents=True)
            (repository / "tests/fixtures/mcp_reference_server.py").touch()
            outbound = _write_outbound_configuration(root / "state", repository)
            ingress = _write_ingress_configuration(root / "state")
            self.assertEqual(0o600, os.stat(outbound).st_mode & 0o777)
            self.assertEqual(0o600, os.stat(ingress).st_mode & 0o777)
            outbound_document = json.loads(outbound.read_text())
            ingress_document = json.loads(ingress.read_text())
            self.assertEqual(
                ["fam-test://document"],
                outbound_document["servers"][0]["allowed_resource_uris"],
            )
            self.assertEqual(
                [{"parameter": "query", "source": "prompt"}],
                outbound_document["servers"][0]["tools"][0]["argument_bindings"],
            )
            self.assertEqual(
                ["fam.ask", "fam.ask.verified"],
                ingress_document["clients"][0]["capabilities"],
            )

    def test_mcp_qualification_uses_canonical_capability_hashes(self):
        self.assertEqual(
            "mcp.phase23-reference.resource.7cfbc1a1450ead42cc09",
            _resource_capability_id(),
        )
        self.assertEqual(
            "fam_42b45fe1f9052b202c6306a3",
            _ingress_tool_name("fam.ask"),
        )
        self.assertEqual(
            "mcp.phase23-reference.tool.29a1af58c13827407626",
            _tool_capability_id("lookup"),
        )

    def test_escalation_evidence_uses_authoritative_provider_models(self) -> None:
        runtime = Mock()
        runtime.loaded_models.return_value = (
            Mock(model_ref="unrelated:latest"),
            Mock(model_ref="gemma4:26b"),
        )
        self.assertEqual(("gemma4:26b",), _known_provider_models(runtime))

    def test_candidate_start_failure_crashes_partial_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = Mock()
            installation.prefix = root / "candidate"
            service = CandidateService(
                installation, root / "state", root / "run",
                ollama_url="http://127.0.0.1:11435",
                source_model_root=root / "source-models",
                manage_ollama=True,
            )
            self.assertEqual(300, service.startup_timeout_seconds)
            process = Mock()
            try:
                with (
                    patch(
                        "tools.phase23_installed_matrix.service.subprocess.Popen",
                        return_value=process,
                    ),
                    patch.object(
                        service, "wait_ready",
                        side_effect=TimeoutError("startup deadline"),
                    ) as wait_ready,
                    patch.object(service, "crash") as crash,
                    patch.object(
                        service, "_stop_orphaned_managed_provider",
                    ) as stop_provider,
                ):
                    with self.assertRaisesRegex(TimeoutError, "startup deadline"):
                        service.start()
                crash.assert_called_once_with()
                stop_provider.assert_called_once_with()
                wait_ready.assert_called_once_with(300)
            finally:
                if service._stdout is not None:
                    service._stdout.close()
                if service._stderr is not None:
                    service._stderr.close()

    def test_candidate_forwards_explicit_validation_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = Mock()
            installation.prefix = root / "candidate"
            (installation.prefix / "bin").mkdir(parents=True)
            service = CandidateService(
                installation, root / "state", root / "run",
                ollama_url="http://127.0.0.1:11435",
                source_model_root=root / "source-models",
                manage_ollama=True,
                validation_profile="compat-cpu-16gb",
            )
            process = Mock()
            try:
                with (
                    patch(
                        "tools.phase23_installed_matrix.service.subprocess.Popen",
                        return_value=process,
                    ) as spawn,
                    patch.object(service, "wait_ready"),
                ):
                    service.start()
                command = spawn.call_args.args[0]
                self.assertEqual("-c", command[1])
                index = command.index("--validation-profile")
                self.assertEqual("compat-cpu-16gb", command[index + 1])
                environment = spawn.call_args.kwargs["env"]
                self.assertEqual(
                    str(installation.prefix / "active/python"),
                    environment["PYTHONPATH"],
                )
            finally:
                if service._stdout is not None:
                    service._stdout.close()
                if service._stderr is not None:
                    service._stderr.close()

    def test_factory_evidence_json_default_serializes_typed_records(self) -> None:
        @dataclass(frozen=True)
        class Record:
            name: str
            created_at: datetime

        instant = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
        self.assertEqual(
            {"name": "activation", "created_at": instant},
            _json_default(Record("activation", instant)),
        )
        self.assertEqual(instant.isoformat(), _json_default(instant))

    def test_factory_process_exposes_only_candidate_product_python(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            repository.mkdir()
            installation = Mock()
            installation.prefix = root / "candidate"
            candidate_python = installation.prefix / "active/python"
            candidate_python.mkdir(parents=True)
            work = root / "work"
            work.mkdir()

            def complete(command, **_kwargs):
                output = Path(command[command.index("--output") + 1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text('{"passed": true}\n')
                return Mock(returncode=0)

            with (
                patch(
                    "tools.phase23_installed_matrix.factory_scenario._stage_factory_state",
                ),
                patch(
                    "tools.phase23_installed_matrix.factory_scenario.subprocess.run",
                    side_effect=complete,
                ) as run,
            ):
                result = run_factory_scenario(
                    installation=installation,
                    repository=repository,
                    root=work,
                    run_id="phase23-installed-test",
                    ollama_url="http://127.0.0.1:11434",
                )
            self.assertTrue(result["passed"])
            self.assertEqual(
                str(candidate_python), run.call_args.kwargs["env"]["PYTHONPATH"],
            )

    def test_fault_window_exposes_only_candidate_product_python(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = Mock()
            installation.prefix = root / "candidate"
            candidate_python = installation.prefix / "active/python"
            candidate_python.mkdir(parents=True)
            with patch(
                "tools.phase23_installed_matrix.application_scenario.subprocess.run",
            ) as run:
                _inject_fault_window(
                    installation,
                    root / "repository",
                    root / "state",
                    root / "runtime",
                    root / "home",
                    "session-1",
                    root / "target",
                    "http://127.0.0.1:11434",
                    root / "models",
                    root / "evidence.json",
                )
            self.assertEqual(
                str(candidate_python), run.call_args.kwargs["env"]["PYTHONPATH"],
            )

    def test_settings_require_new_absolute_output_and_safe_run_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            models = root / "models"
            repository.mkdir()
            models.mkdir()
            settings = InstalledMatrixSettings(
                repository, root / "output", "phase23-installed-01",
                source_model_root=models,
            )
            self.assertEqual("phase23-installed-01", settings.run_id)
            with self.assertRaisesRegex(ValueError, "identity"):
                InstalledMatrixSettings(
                    repository, root / "other", "unsafe/id",
                    source_model_root=models,
                )

    def test_final_evidence_requires_every_named_pass_and_operational_cleanup(self):
        document = {
            "scenarios": {
                item.value: {"passed": True} for item in REQUIRED_SCENARIOS
            },
            "complete_removal": True,
            "live_owner_service_preserved": True,
        }
        finalize(document)
        self.assertTrue(document["passed"])
        document["scenarios"][REQUIRED_SCENARIOS[0].value]["passed"] = False
        finalize(document)
        self.assertFalse(document["passed"])

    def test_expert_restriction_rejects_a_non_candidate_import(self):
        class _Installation:
            prefix = Path("/candidate")

        with self.assertRaisesRegex(RuntimeError, "candidate expert restriction failed"):
            restrict_candidate_experts(
                _Installation(), Path("/repository"), Path("/state"),
                Path("/output"), "model:tag",
            )


if __name__ == "__main__":
    unittest.main()
