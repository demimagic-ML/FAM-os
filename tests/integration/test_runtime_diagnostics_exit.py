"""Real systemd/Bubblewrap runtime-diagnostics execution fixtures."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.bubblewrap.diagnostics import BubblewrapRuntimeDiagnosticAdapter
from fam_os.adapters.bubblewrap.engineering import (
    EngineeringSandboxAdapter,
    toolchain_tree_sha256,
)
from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier,
    sign_recipe_specification,
)
from fam_os.core.engineering import (
    DiagnosticArtifactKind,
    EngineeringEcosystem,
    RuntimeDiagnosticKind,
    RuntimeDiagnosticRecipePolicy,
    RuntimeDiagnosticStatus,
    RuntimeDiagnosticPhase,
    RuntimePerformanceMode,
    ToolRecipePurpose,
    ToolchainMount,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import (
    ToolRecipeSpecification,
    diagnostic_recipe_specifications,
)
from tests.contract.schema_diagnostics_fixtures import diagnostics_schema_values
from tests.contract.schema_execution_fixtures import execution_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values


TOOLS_PRESENT = all(shutil.which(item) for item in ("python3", "bwrap", "systemd-run"))


@unittest.skipUnless(TOOLS_PRESENT, "runtime diagnostic containment tools unavailable")
class RuntimeDiagnosticsExitTests(unittest.TestCase):
    def setUp(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        specification = ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.STACK_TRACE,
            "/usr/bin/python3", ("-X", "faulthandler", "{diagnostic_target}"),
            "verifier.engineering.python.stack-trace.v1",
        )
        self.recipe = sign_recipe_specification(
            specification, "diagnostic-key", private_key,
        )
        performance = ToolRecipeSpecification(
            EngineeringEcosystem.C, ToolRecipePurpose.PERFORMANCE_REGRESSION,
            "/usr/bin/time", ("-p", "{diagnostic_target}"),
            "verifier.engineering.runtime.performance-regression.v1",
        )
        self.performance_recipe = sign_recipe_specification(
            performance, "diagnostic-key", private_key,
        )
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "diagnostic-key": private_key.public_key(),
        }))
        catalog.admit(self.recipe)
        catalog.admit(self.performance_recipe)
        tool = Path("src/fam_os/adapters/diagnostics/tool.py").resolve()
        mount = ToolchainMount(
            str(tool), "/opt/fam/toolchains/diagnostics/tool.py",
            toolchain_tree_sha256(tool),
        )
        self.release_recipes = {}
        for item in diagnostic_recipe_specifications():
            if item.purpose is ToolRecipePurpose.PERFORMANCE_REGRESSION:
                continue
            mounts = (mount,) if "/opt/fam/toolchains/diagnostics/tool.py" in item.argv else ()
            signed = sign_recipe_specification(
                item, "diagnostic-key", private_key, toolchain_mounts=mounts,
            )
            catalog.admit(signed)
            self.release_recipes[item.purpose] = signed
        policy = RuntimeDiagnosticRecipePolicy(catalog)
        sandbox = EngineeringSandboxAdapter(catalog)
        self.adapter = BubblewrapRuntimeDiagnosticAdapter(policy, sandbox)

    def test_real_candidate_run_redacts_and_persists_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "program.py").write_text(
                "print('trace token=physical-secret')\n", encoding="utf-8",
            )
            request, candidate, profile = self._values(root, "program.py")
            receipt = self.adapter.run(
                request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            artifact = root / receipt.artifacts[0].artifact_id
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, receipt.status)
            self.assertEqual(0o600, artifact.stat().st_mode & 0o777)
            self.assertIn("[REDACTED]", artifact.read_text(encoding="utf-8"))
            self.assertNotIn("physical-secret", artifact.read_text(encoding="utf-8"))

    def test_real_output_flood_fails_without_persisting_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "flood.py").write_text("print('x' * 100000)\n", encoding="utf-8")
            request, candidate, profile = self._values(root, "flood.py")
            request = replace(
                request, limits=replace(request.limits, output_bytes=512),
            )
            profile = replace(profile, output_bytes=512)
            receipt = self.adapter.run(
                request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.UNAVAILABLE, receipt.status)
            self.assertEqual((), receipt.artifacts)
            self.assertFalse((root / ".fam").exists())

    def test_symlink_target_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "link.py").symlink_to("real.py")
            request, candidate, profile = self._values(root, "link.py")
            with self.assertRaisesRegex(PermissionError, "contains a symlink"):
                self.adapter.run(
                    request, candidate, profile,
                    authorization_decision_ids=("authorization-1",),
                )

    def test_real_performance_run_binds_parsed_metric_to_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "benchmark.py"
            target.write_text(
                "#!/usr/bin/python3\nimport time\ntime.sleep(0.05)\n",
                encoding="utf-8",
            )
            target.chmod(0o700)
            request, candidate, profile = self._values(root, target.name)
            capture = replace(
                request, request_id="diagnostic-performance-baseline",
                signed_recipe_id=self.performance_recipe.recipe_id,
                signed_recipe_version=self.performance_recipe.recipe_version,
                recipe_payload_sha256=self.performance_recipe.payload_sha256,
                phase=RuntimeDiagnosticPhase.BASELINE,
                kind=RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
                artifact_kinds=(DiagnosticArtifactKind.PERFORMANCE_SAMPLE,),
                baseline_artifact_sha256=None,
                baseline_value_microunits=None,
                maximum_regression_ppm=1_000_000,
                performance_mode=RuntimePerformanceMode.BASELINE_CAPTURE,
            )
            baseline = self.adapter.run(
                capture, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, baseline.status)
            self.assertEqual(
                baseline.artifacts[0].sha256,
                baseline.baseline_artifact_sha256,
            )
            request = replace(
                request, signed_recipe_id=self.performance_recipe.recipe_id,
                signed_recipe_version=self.performance_recipe.recipe_version,
                recipe_payload_sha256=self.performance_recipe.payload_sha256,
                kind=RuntimeDiagnosticKind.PERFORMANCE_REGRESSION,
                artifact_kinds=(DiagnosticArtifactKind.PERFORMANCE_SAMPLE,),
                baseline_artifact_sha256=baseline.baseline_artifact_sha256,
                baseline_value_microunits=baseline.observed_value_microunits,
                maximum_regression_ppm=1_000_000,
                performance_mode=RuntimePerformanceMode.COMPARISON,
            )
            receipt = self.adapter.run(
                request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, receipt.status)
            self.assertGreater(receipt.observed_value_microunits, 0)
            self.assertLessEqual(receipt.regression_ppm, 1_000_000)
            failing = replace(
                request, request_id="diagnostic-performance-regression-fail",
                baseline_artifact_sha256="e" * 64,
                baseline_value_microunits=1,
            )
            failed_receipt = self.adapter.run(
                failing, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.FAILED, failed_receipt.status)
            self.assertGreater(failed_receipt.regression_ppm, 0)

    def test_real_leak_sanitizer_accepts_clean_and_rejects_leaking_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clean.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
            (root / "leak.c").write_text(
                "#include <stdlib.h>\nint main(void){void *p=malloc(32);(void)p;return 0;}\n",
                encoding="utf-8",
            )
            clean_request, candidate, profile = self._values(root, "clean.c")
            clean_request = self._release_request(
                clean_request, ToolRecipePurpose.LEAK_DETECTION,
                RuntimeDiagnosticKind.LEAK_DETECTION,
                DiagnosticArtifactKind.LEAK_REPORT, "leak-clean",
            )
            clean = self.adapter.run(
                clean_request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            clean_output = (root / clean.artifacts[0].artifact_id).read_text()
            self.assertEqual(
                RuntimeDiagnosticStatus.PASSED, clean.status,
                f"exit={clean.exit_code} output={clean_output}",
            )
            leak_request, _candidate, _profile = self._values(root, "leak.c")
            leak_request = self._release_request(
                leak_request, ToolRecipePurpose.LEAK_DETECTION,
                RuntimeDiagnosticKind.LEAK_DETECTION,
                DiagnosticArtifactKind.LEAK_REPORT, "leak-detected",
            )
            leaking = self.adapter.run(
                leak_request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.FAILED, leaking.status)
            self.assertIn("LeakSanitizer", (root / leaking.artifacts[0].artifact_id).read_text())

    def test_thread_sanitizer_accepts_clean_and_rejects_race_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clean.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
            (root / "race.c").write_text(
                "#include <pthread.h>\nint value;\n"
                "void *write_value(void *unused){(void)unused;value++;return 0;}\n"
                "int main(void){pthread_t a,b;pthread_create(&a,0,write_value,0);"
                "pthread_create(&b,0,write_value,0);pthread_join(a,0);pthread_join(b,0);return 0;}\n",
                encoding="utf-8",
            )
            clean_request, candidate, profile = self._values(root, "clean.c")
            clean_request = self._release_request(
                clean_request, ToolRecipePurpose.RACE_DETECTION,
                RuntimeDiagnosticKind.RACE_DETECTION,
                DiagnosticArtifactKind.RACE_REPORT, "race-clean",
            )
            clean = self.adapter.run(
                clean_request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            clean_output = (root / clean.artifacts[0].artifact_id).read_text()
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, clean.status, clean_output)
            race_request, _candidate, _profile = self._values(root, "race.c")
            race_request = self._release_request(
                race_request, ToolRecipePurpose.RACE_DETECTION,
                RuntimeDiagnosticKind.RACE_DETECTION,
                DiagnosticArtifactKind.RACE_REPORT, "race-detected",
            )
            racing = self.adapter.run(
                race_request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            race_output = (root / racing.artifacts[0].artifact_id).read_text()
            self.assertEqual(RuntimeDiagnosticStatus.FAILED, racing.status)
            self.assertIn("ThreadSanitizer", race_output)

    def test_ephemeral_core_dump_is_analyzed_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "crash.c"
            target = root / "crash"
            source.write_text(
                "int main(void){volatile int *p=(int *)0;*p=1;return 0;}\n",
                encoding="utf-8",
            )
            subprocess.run(
                ("/usr/bin/gcc", "-g", "-o", str(target), str(source)),
                check=True, capture_output=True, timeout=20,
            )
            request, candidate, profile = self._values(root, target.name)
            request = self._release_request(
                request, ToolRecipePurpose.CRASH_DUMP,
                RuntimeDiagnosticKind.CRASH_DUMP,
                DiagnosticArtifactKind.CRASH_DUMP, "core-generated",
            )
            receipt = self.adapter.run(
                request, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            output = (root / receipt.artifacts[0].artifact_id).read_text()
            self.assertEqual(RuntimeDiagnosticStatus.PASSED, receipt.status, output)
            self.assertIn("Saved corefile", output)
            self.assertNotIn(str(root), output)
            self.assertFalse(any(root.rglob("*.core")))
            clean_source = root / "clean_core.c"
            clean_target = root / "clean_core"
            clean_source.write_text("int main(void){return 0;}\n", encoding="utf-8")
            subprocess.run(
                ("/usr/bin/gcc", "-g", "-o", str(clean_target), str(clean_source)),
                check=True, capture_output=True, timeout=20,
            )
            negative, _candidate, _profile = self._values(root, clean_target.name)
            negative = self._release_request(
                negative, ToolRecipePurpose.CRASH_DUMP,
                RuntimeDiagnosticKind.CRASH_DUMP,
                DiagnosticArtifactKind.CRASH_DUMP, "core-not-generated",
            )
            failed = self.adapter.run(
                negative, candidate, profile,
                authorization_decision_ids=("authorization-1",),
            )
            self.assertEqual(RuntimeDiagnosticStatus.FAILED, failed.status)
            self.assertIn(
                "not generated", (root / failed.artifacts[0].artifact_id).read_text(),
            )

    def test_real_debug_trace_cpu_and_memory_positive_negative_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "targets.c"
            source.write_text(
                "#include <string.h>\nint main(int n,char **v){"
                "if(n>1&&!strcmp(v[1],\"crash\")){*(volatile int*)0=1;}"
                "return n>1&&!strcmp(v[1],\"fail\");}\n",
                encoding="utf-8",
            )
            for name, define in (("clean", ""), ("crash", "crash"), ("fail", "fail")):
                wrapper = root / f"{name}.c"
                wrapper.write_text(
                    source.read_text() if not define else source.read_text().replace(
                        "int main(int n,char **v)",
                        f"int target_main(int n,char **v)"
                    ) + f"\nint main(void){{char *v[]={{\"x\",\"{define}\"}};return target_main(2,v);}}\n",
                    encoding="utf-8",
                )
                subprocess.run(
                    ("/usr/bin/gcc", "-g", "-o", str(root / name), str(wrapper)),
                    check=True, capture_output=True, timeout=20,
                )
            (root / "bench.py").write_text("sum(range(1000))\n", encoding="utf-8")
            (root / "python_fail.py").write_text("raise RuntimeError('expected')\n", encoding="utf-8")
            pairs = (
                (ToolRecipePurpose.STACK_TRACE, RuntimeDiagnosticKind.STACK_TRACE, DiagnosticArtifactKind.STACK_TRACE, "crash", "clean"),
                (ToolRecipePurpose.TRACE, RuntimeDiagnosticKind.TRACE, DiagnosticArtifactKind.TRACE, "clean", "fail"),
                (ToolRecipePurpose.CPU_PROFILE, RuntimeDiagnosticKind.CPU_PROFILE, DiagnosticArtifactKind.PROFILE, "bench.py", "python_fail.py"),
                (ToolRecipePurpose.MEMORY_PROFILE, RuntimeDiagnosticKind.MEMORY_PROFILE, DiagnosticArtifactKind.PROFILE, "bench.py", "python_fail.py"),
            )
            for purpose, kind, artifact, positive_target, negative_target in pairs:
                with self.subTest(kind=kind.value):
                    positive, candidate, profile = self._values(root, positive_target)
                    positive = self._release_request(
                        positive, purpose, kind, artifact, f"{kind.value}-positive",
                    )
                    passed = self.adapter.run(
                        positive, candidate, profile,
                        authorization_decision_ids=("authorization-1",),
                    )
                    passed_output = (root / passed.artifacts[0].artifact_id).read_text()
                    self.assertEqual(
                        RuntimeDiagnosticStatus.PASSED, passed.status,
                        f"exit={passed.exit_code} output={passed_output}",
                    )
                    negative, _candidate, _profile = self._values(root, negative_target)
                    negative = self._release_request(
                        negative, purpose, kind, artifact, f"{kind.value}-negative",
                    )
                    failed = self.adapter.run(
                        negative, candidate, profile,
                        authorization_decision_ids=("authorization-1",),
                    )
                    self.assertEqual(RuntimeDiagnosticStatus.FAILED, failed.status)

    def _values(self, root: Path, target: str):
        candidate = replace(
            transaction_schema_values()[2], candidate_workspace=str(root),
        )
        profile = replace(
            execution_schema_values()[1], wall_seconds=10, cpu_seconds=2,
            output_bytes=1_048_576,
            sanitized_environment=(),
        )
        request, _receipt = diagnostics_schema_values()
        request = replace(
            request, request_id=f"diagnostic-{target}",
            signed_recipe_id=self.recipe.recipe_id,
            signed_recipe_version=self.recipe.recipe_version,
            recipe_payload_sha256=self.recipe.payload_sha256,
            kind=RuntimeDiagnosticKind.STACK_TRACE,
            target_argv=(target,), allowed_environment_keys=(),
            artifact_kinds=(DiagnosticArtifactKind.STACK_TRACE,),
            limits=replace(
                request.limits, wall_seconds=10, cpu_seconds=2,
                output_bytes=1_048_576, artifact_bytes=1_048_576,
            ), baseline_artifact_sha256=None,
            baseline_value_microunits=None, maximum_regression_ppm=None,
            created_at=datetime.now(timezone.utc),
            performance_mode=RuntimePerformanceMode.NOT_APPLICABLE,
        )
        return request, candidate, profile

    def _release_request(self, request, purpose, kind, artifact_kind, request_id):
        recipe = self.release_recipes[purpose]
        limits = request.limits
        if kind in {
            RuntimeDiagnosticKind.CRASH_DUMP,
            RuntimeDiagnosticKind.STACK_TRACE,
            RuntimeDiagnosticKind.RACE_DETECTION,
            RuntimeDiagnosticKind.LEAK_DETECTION,
        }:
            limits = replace(limits, unbounded_virtual_address_space=True)
        return replace(
            request, request_id=request_id,
            signed_recipe_id=recipe.recipe_id,
            signed_recipe_version=recipe.recipe_version,
            recipe_payload_sha256=recipe.payload_sha256, kind=kind,
            limits=limits,
            artifact_kinds=(artifact_kind,), baseline_artifact_sha256=None,
            baseline_value_microunits=None, maximum_regression_ppm=None,
        )


if __name__ == "__main__":
    unittest.main()
