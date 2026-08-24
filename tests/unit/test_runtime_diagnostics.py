import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier,
    sign_recipe_specification,
)
from fam_os.adapters.bubblewrap.diagnostics import (
    BubblewrapRuntimeDiagnosticAdapter,
    PosixTimeMetricParser,
)
from fam_os.adapters.bubblewrap.engineering import EngineeringSandboxAdapter

from fam_os.core.engineering import (
    RuntimeDiagnosticKind,
    RuntimeDiagnosticPhase,
    RuntimeDiagnosticRecipePolicy,
    RuntimeDiagnosticStatus,
    RuntimePerformanceMode,
    SandboxNetworkMode,
    validate_runtime_diagnostic_receipt,
    DiagnosticArtifactKind,
    EngineeringEcosystem,
    ToolRecipePurpose,
    ToolQualificationStatus,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification
from fam_os.core.engineering.production_recipes import diagnostic_recipe_specifications
from fam_os.verification.sandbox import IsolationLevel, SandboxResult, SandboxStatus
from tests.contract.schema_execution_fixtures import execution_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values
from tests.contract.schema_diagnostic_qualification_fixtures import diagnostic_qualification_schema_values
from tests.contract.schema_diagnostics_fixtures import diagnostics_schema_values


class RuntimeDiagnosticContractTests(unittest.TestCase):
    def test_performance_baseline_capture_binds_its_sanitized_measurement_artifact(self):
        request, receipt = diagnostics_schema_values()
        capture = replace(
            request, phase=RuntimeDiagnosticPhase.BASELINE,
            baseline_artifact_sha256=None, baseline_value_microunits=None,
            performance_mode=RuntimePerformanceMode.BASELINE_CAPTURE,
        )
        captured = replace(
            receipt, baseline_artifact_sha256=receipt.artifacts[0].sha256,
            observed_value_microunits=1_000_000, regression_ppm=0,
            performance_mode=RuntimePerformanceMode.BASELINE_CAPTURE,
        )
        validate_runtime_diagnostic_receipt(capture, captured)

    def test_performance_request_and_receipt_bind_exact_baseline(self) -> None:
        request, receipt = diagnostics_schema_values()
        self.assertEqual(RuntimeDiagnosticKind.PERFORMANCE_REGRESSION, request.kind)
        self.assertEqual(request.baseline_artifact_sha256, receipt.baseline_artifact_sha256)
        validate_runtime_diagnostic_receipt(request, receipt)

    def test_performance_request_rejects_missing_baseline(self) -> None:
        request, _receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "exact baseline"):
            replace(request, baseline_artifact_sha256=None)

    def test_request_rejects_host_secret_environment(self) -> None:
        request, _receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "credentials or home"):
            replace(request, allowed_environment_keys=("GITHUB_TOKEN",))

    def test_network_policy_requires_exact_destinations(self) -> None:
        request, _receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "exact destinations"):
            replace(request, network_mode=SandboxNetworkMode.ALLOWLIST_PROXY)

    def test_virtual_address_exception_is_rejected_for_performance(self) -> None:
        request, _receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "debugger-or-sanitizer-only"):
            replace(
                request,
                limits=replace(
                    request.limits, unbounded_virtual_address_space=True,
                ),
            )

    def test_passing_receipt_rejects_nonzero_exit(self) -> None:
        _request, receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "exit code zero"):
            replace(receipt, status=RuntimeDiagnosticStatus.PASSED, exit_code=1)

    def test_receipt_rejects_partial_performance_evidence(self) -> None:
        _request, receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "must be complete"):
            replace(receipt, regression_ppm=None)

    def test_cross_contract_validation_rejects_identity_and_bound_mismatch(self) -> None:
        request, receipt = diagnostics_schema_values()
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_runtime_diagnostic_receipt(request, replace(receipt, candidate_id="other"))
        with self.assertRaisesRegex(ValueError, "passing threshold"):
            validate_runtime_diagnostic_receipt(
                request, replace(receipt, regression_ppm=request.maximum_regression_ppm + 1),
            )

    def test_signed_recipe_policy_binds_exact_diagnostic_kind_and_digest(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        specification = ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.STACK_TRACE,
            "/usr/bin/python3", ("-X", "faulthandler", "program.py"),
            "verifier.engineering.python.stack-trace.v1",
        )
        recipe = sign_recipe_specification(specification, "diagnostic-key", private_key)
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "diagnostic-key": private_key.public_key(),
        }))
        catalog.admit(recipe)
        request, _receipt = diagnostics_schema_values()
        request = replace(
            request, signed_recipe_id=recipe.recipe_id,
            signed_recipe_version=recipe.recipe_version,
            recipe_payload_sha256=recipe.payload_sha256,
            kind=RuntimeDiagnosticKind.STACK_TRACE,
            allowed_environment_keys=(),
            artifact_kinds=(DiagnosticArtifactKind.STACK_TRACE,),
            baseline_artifact_sha256=None, baseline_value_microunits=None,
            maximum_regression_ppm=None,
            performance_mode=RuntimePerformanceMode.NOT_APPLICABLE,
        )
        policy = RuntimeDiagnosticRecipePolicy(catalog)
        self.assertEqual(recipe, policy.admit(request))
        with self.assertRaisesRegex(PermissionError, "purpose"):
            policy.admit(replace(request, kind=RuntimeDiagnosticKind.TRACE))
        with self.assertRaisesRegex(PermissionError, "digest"):
            policy.admit(replace(request, recipe_payload_sha256="f" * 64))

    def test_release_specs_cover_every_diagnostic_kind_with_one_target(self) -> None:
        specifications = diagnostic_recipe_specifications()
        self.assertEqual(set(ToolRecipePurpose) - {
            ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT,
            ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.TYPE_CHECK,
            ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.COVERAGE,
            ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS,
            ToolRecipePurpose.ACCEPTANCE,
        }, {item.purpose for item in specifications})
        self.assertTrue(all(item.argv.count("{diagnostic_target}") == 1 for item in specifications))

    def test_posix_time_parser_is_exact_and_rejects_ambiguous_metrics(self) -> None:
        parser = PosixTimeMetricParser()
        self.assertEqual(1_250_000, parser.parse_microunits("real 1.25\nuser 1.00\n"))
        with self.assertRaisesRegex(ValueError, "one POSIX"):
            parser.parse_microunits("real 1.0\nreal 2.0\n")

    def test_qualification_matrix_rejects_missing_or_failed_kind(self) -> None:
        _qualification, matrix = diagnostic_qualification_schema_values()
        with self.assertRaisesRegex(ValueError, "every kind"):
            replace(matrix, qualifications=matrix.qualifications[:-1])
        failed = replace(
            matrix.qualifications[0],
            status=ToolQualificationStatus.FAILED,
        )
        with self.assertRaisesRegex(ValueError, "failed tools"):
            replace(matrix, qualifications=(failed, *matrix.qualifications[1:]))

    def test_concrete_adapter_stores_only_sanitized_candidate_evidence(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        specification = ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.STACK_TRACE,
            "/usr/bin/python3", ("-X", "faulthandler", "{diagnostic_target}"),
            "verifier.engineering.python.stack-trace.v1",
        )
        recipe = sign_recipe_specification(specification, "diagnostic-key", private_key)
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "diagnostic-key": private_key.public_key(),
        }))
        catalog.admit(recipe)
        policy = RuntimeDiagnosticRecipePolicy(catalog)
        launcher = _DiagnosticLauncher()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "program.py").write_text("raise RuntimeError('fixture')\n")
            candidate = replace(
                transaction_schema_values()[2], candidate_workspace=str(root),
            )
            profile = replace(
                execution_schema_values()[1], wall_seconds=10, cpu_seconds=2,
                output_bytes=4096,
                sanitized_environment=(),
            )
            request, _receipt = diagnostics_schema_values()
            request = replace(
                request, signed_recipe_id=recipe.recipe_id,
                signed_recipe_version=recipe.recipe_version,
                recipe_payload_sha256=recipe.payload_sha256,
                kind=RuntimeDiagnosticKind.STACK_TRACE,
                target_argv=("program.py",), allowed_environment_keys=(),
                artifact_kinds=(DiagnosticArtifactKind.STACK_TRACE,),
                limits=replace(
                    request.limits, wall_seconds=10, cpu_seconds=2,
                    output_bytes=4096, artifact_bytes=4096,
                ), baseline_artifact_sha256=None,
                baseline_value_microunits=None, maximum_regression_ppm=None,
                performance_mode=RuntimePerformanceMode.NOT_APPLICABLE,
            )
            sandbox = EngineeringSandboxAdapter(catalog, launcher=launcher)
            adapter = BubblewrapRuntimeDiagnosticAdapter(
                policy, sandbox, launcher=launcher,
                clock=lambda: datetime(2026, 7, 19, tzinfo=timezone.utc),
            )
            receipt = adapter.run(
                request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            artifact_path = root / receipt.artifacts[0].artifact_id
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, receipt.status)
            self.assertIn("[REDACTED]", artifact_path.read_text())
            self.assertNotIn("super-secret", artifact_path.read_text())
            self.assertIn("--unshare-all", launcher.calls[0][0])


class _DiagnosticLauncher:
    def __init__(self) -> None:
        self.calls = []

    def run(self, command, limits, environment, isolation):
        self.calls.append((command, limits, environment, isolation))
        return SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1,
            "trace token=super-secret", "", 0,
        )


if __name__ == "__main__":
    unittest.main()
