"""Run the real product release boundary through removal and audit retention."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fam_os
from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.expert_factory import ConversionOutputType
from fam_os.product.composition.factory_release import FactoryReleaseRuntimeSettings
from fam_os.product.service import LocalProductService, ProductServiceSettings
from tools.phase22_release_exit.evidence import write_release_evidence
from tools.phase22_release_exit.settings import SpecialistReleaseExitPaths
from tools.phase22_release_exit.suite import materialize_canary_suite


GIB = 1024**3
SPECIALIST_CAPABILITIES = ("code.generate.python",)


def run_release_exit(
    *, paths: SpecialistReleaseExitPaths, run_id: str, llama_cpp_revision: str,
    ollama_url: str, release_attempt_id: str,
) -> dict[str, object]:
    if len(llama_cpp_revision) != 40:
        raise ValueError("llama.cpp revision must be an immutable commit")
    root = paths.release_root(release_attempt_id)
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    suite = root / "canary-suite.jsonl"
    suite_evidence = materialize_canary_suite(
        prompt_configuration=paths.prompt_configuration,
        verifier_tests=paths.verifier_tests, target=suite,
    )
    settings = FactoryReleaseRuntimeSettings(
        conversion_environment=paths.conversion_environment,
        conversion_wheelhouse_manifest=paths.conversion_manifest,
        llama_cpp_directory=paths.llama_cpp,
        llama_cpp_revision=llama_cpp_revision,
        model_directory=paths.model_directory,
        training_workspace_root=paths.training_jobs,
        conversion_workspace_root=root / "conversion",
        package_output_root=root / "packages",
        package_artifact_root=root / "installed",
        package_lifecycle_state=root / "lifecycle.json",
        canary_workspace_root=root / "canary",
        canary_suite=suite,
        ollama_executable=paths.ollama,
        ollama_url=ollama_url,
    )
    runtime = OllamaRuntime(OllamaSettings(ollama_url, 600))
    service = LocalProductService(
        ProductServiceSettings(
            state_root=paths.state_root,
            runtime_root=(
                Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}"))
                / f"fam-p22-{release_attempt_id}"
            ),
            model_ref="qwen3:1.7b",
            ollama_url=ollama_url,
            console_port=0,
            manage_ollama=False,
            ollama_executable=paths.ollama,
            device_display_name="FAM Phase 22 release qualifier",
            factory_release_runtime=settings,
        ),
        runtime=runtime,
    )
    try:
        service.start()
        control = service.factory_control
        release = service.factory_release_services
        if control is None or release is None:
            raise RuntimeError("factory release services were not composed")
        decisions = tuple(control.evaluation_decisions())
        decision = next(
            (item for item in decisions if item.evaluation_id == f"{run_id}-evaluation"),
            None,
        )
        if decision is None or not decision.promotable:
            raise PermissionError("promotable specialist decision is unavailable")
        environment = release.conversions.probe_environment()
        attempt_scope = f"{run_id}-{release_attempt_id}"
        conversion_id = f"{attempt_scope}-conversion"
        approval = release.conversions.issue(
            request_id=conversion_id,
            evaluation_id=decision.evaluation_id,
            environment_sha256=environment.manifest_sha256,
            base_output_type=ConversionOutputType.Q8_0,
            adapter_output_type=ConversionOutputType.F16,
            runtime_model_ref=f"fam-stable-toposort:{release_attempt_id}",
            maximum_output_bytes=6 * GIB,
            maximum_wall_seconds=3_600,
            maximum_ram_bytes=32 * GIB,
            maximum_cpu_cores=20,
            one_use_conversion_id=conversion_id,
            lifetime_seconds=7_200,
            confirmed=True,
        )
        conversion = release.conversions.run(
            approval_id=approval.approval_id, confirmed=True,
        )
        if conversion.status.value != "completed":
            raise RuntimeError(f"specialist conversion failed: {conversion.reason_code}")
        release_id = f"{attempt_scope}-release"
        package = release.releases.package(
            release_id=release_id,
            conversion_id=conversion.conversion_id,
            package_id="fam.specialist.stable-toposort",
            package_version=f"1.0.0-{release_attempt_id}",
            expert_id="fam.expert.stable-toposort",
            declared_capabilities=SPECIALIST_CAPABILITIES,
            required_verifier_ids=("python.deterministic-tests.v1",),
            tokenizer_path=paths.model_directory / "tokenizer.json",
            chat_template_path=paths.model_directory / "tokenizer_config.json",
            confirmed=True,
        )
        canary_id = f"{attempt_scope}-canary"
        canary_approval = release.canary_approvals.issue(
            request_id=canary_id,
            package_receipt_id=package.receipt_id,
            suite_path=suite,
            verifier_id="python.deterministic-tests.v1",
            maximum_output_tokens=1_024,
            maximum_wall_seconds=600,
            maximum_ram_bytes=16 * GIB,
            maximum_vram_bytes=15 * GIB,
            one_use_canary_id=canary_id,
            lifetime_seconds=3_600,
            confirmed=True,
        )
        activation_decision = release.canary_runner.run(
            approval_id=canary_approval.approval_id, confirmed=True,
        )
        if not activation_decision.activate:
            raise RuntimeError(
                "specialist canary denied activation: "
                + ",".join(activation_decision.reason_codes)
            )
        activated = release.activation.activate(
            canary_id=canary_id, confirmed=True,
        )
        rollback = release.lifecycle.manual_rollback(
            request_id=f"{attempt_scope}-manual-rollback",
            release_id=release_id,
            target_release_id=None,
            expected_lifecycle_revision=activated.revision,
            reason_code="qualification.manual_rollback",
            confirmed=True,
        )
        reactivated = release.activation.activate(
            canary_id=canary_id, confirmed=True,
        )
        retirement = release.lifecycle.retire(
            request_id=f"{attempt_scope}-retirement",
            release_id=release_id,
            expected_lifecycle_revision=reactivated.revision,
            reason_code="qualification.retirement",
            remove_artifact=True,
            confirmed=True,
        )
        canary_report = next(
            item for item in control.canary_reports()
            if item.canary_id == canary_id
        )
        evidence = {
            "activation": activation_decision,
            "audit_retained": retirement.audit_retained,
            "canary": canary_report,
            "canary_suite": suite_evidence,
            "conversion": conversion,
            "conversion_environment": environment,
            "package": package,
            "passed": all((
                package.installed_disabled,
                activation_decision.activate,
                canary_report.passed_case_count == canary_report.case_count,
                rollback.runtime_model_removed,
                retirement.runtime_model_removed,
                retirement.artifact_removed,
                retirement.audit_retained,
            )),
            "reactivated_lifecycle_revision": reactivated.revision,
            "retirement": retirement,
            "rollback": rollback,
            "run_id": run_id,
            "product_runtime": _product_runtime_evidence(),
        }
        write_release_evidence(root / "release-evidence.json", evidence)
        return evidence
    finally:
        service.stop()


def _product_runtime_evidence() -> dict[str, str]:
    module_file = fam_os.__file__
    if module_file is None:
        raise RuntimeError("FAM_OS product module path is unavailable")
    path = Path(module_file).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"module_path": str(path), "module_sha256": digest.hexdigest()}
