"""Authenticated owner controls and evidence routes for the Expert Factory."""

from pathlib import Path

from fam_os.console.tasks import task_document
from fam_os.expert_factory import (
    AdapterTrainingMethod,
    AdapterTrainingRecipe,
    ApprovedBaseModel,
    ConversionOutputType,
    TrainingComputeDtype,
    TrainingDataSensitivity,
    HeldOutEvaluationKind,
    HeldOutVerifierKind,
    TrainingResourceBudget,
    TrainingSourceKind,
    build_evaluation_policy,
)


def handle_factory_get(handler, path: str) -> bool:
    if not path.startswith("/api/v1/factory/"):
        return False
    if handler._session() is None:
        handler.send_error(401)
        return True
    factory = handler.server.factory_api
    if factory is None:
        handler._json(503, {"error": "Expert Factory discovery is unavailable."})
        return True
    methods = {
        "/api/v1/factory/traces": ("traces", "traces"),
        "/api/v1/factory/clusters": ("clusters", "clusters"),
        "/api/v1/factory/proposals": ("proposals", "proposals"),
        "/api/v1/factory/sealed-datasets": (
            "sealed_datasets", "sealed_datasets",
        ),
        "/api/v1/factory/leakage-reports": (
            "leakage_reports", "leakage_reports",
        ),
        "/api/v1/factory/training-approvals": (
            "training_approvals", "training_approvals",
        ),
        "/api/v1/factory/training-environments": (
            "training_environments", "training_environments",
        ),
        "/api/v1/factory/training-jobs": (
            "training_jobs", "training_jobs",
        ),
        "/api/v1/factory/training-terminals": (
            "training_terminals", "training_terminals",
        ),
        "/api/v1/factory/training-admissions": (
            "training_admissions", "training_admissions",
        ),
        "/api/v1/factory/evaluation-approvals": (
            "evaluation_approvals", "evaluation_approvals",
        ),
        "/api/v1/factory/held-out-access-receipts": (
            "held_out_access_receipts", "held_out_access_receipts",
        ),
        "/api/v1/factory/evaluation-reports": (
            "evaluation_reports", "evaluation_reports",
        ),
        "/api/v1/factory/evaluation-decisions": (
            "evaluation_decisions", "evaluation_decisions",
        ),
        "/api/v1/factory/conversion-environments": (
            "conversion_environments", "conversion_environments",
        ),
        "/api/v1/factory/conversion-approvals": (
            "conversion_approvals", "conversion_approvals",
        ),
        "/api/v1/factory/conversion-receipts": (
            "conversion_receipts", "conversion_receipts",
        ),
        "/api/v1/factory/release-lineages": (
            "release_lineages", "release_lineages",
        ),
        "/api/v1/factory/package-receipts": (
            "package_receipts", "package_receipts",
        ),
        "/api/v1/factory/canary-approvals": (
            "canary_approvals", "canary_approvals",
        ),
        "/api/v1/factory/canary-reports": (
            "canary_reports", "canary_reports",
        ),
        "/api/v1/factory/activation-decisions": (
            "activation_decisions", "activation_decisions",
        ),
        "/api/v1/factory/specialist-lifecycle-receipts": (
            "specialist_lifecycle_receipts", "specialist_lifecycle_receipts",
        ),
    }
    try:
        selected = methods.get(path)
        if selected is None:
            raise ValueError("factory collection path is invalid")
        name, method_name = selected
        method = getattr(factory, method_name)
        handler._json(200, {name: [task_document(item) for item in method()]})
    except (TypeError, ValueError) as error:
        handler._json(400, {"error": str(error)})
    return True


def handle_factory_post(handler, path: str, document: dict) -> bool:
    if not path.startswith("/api/v1/factory/"):
        return False
    factory = handler.server.factory_api
    if factory is None:
        handler._json(503, {"error": "Expert Factory controls are unavailable."})
        return True
    if path == "/api/v1/factory/capture-grants":
        _exact(document, {
            "request_id", "proposal_id", "capability_id", "source_kinds",
            "workspace_scopes", "sensitivities", "maximum_source_bytes",
            "maximum_examples", "lifetime_seconds", "confirmed",
        })
        value = factory.create_capture_grant(
            request_id=_text(document, "request_id"),
            proposal_id=_text(document, "proposal_id"),
            capability_id=_text(document, "capability_id"),
            source_kinds=tuple(
                TrainingSourceKind(item) for item in _strings(document, "source_kinds")
            ),
            workspace_scopes=_strings(document, "workspace_scopes"),
            sensitivities=tuple(
                TrainingDataSensitivity(item)
                for item in _strings(document, "sensitivities")
            ),
            maximum_source_bytes=_integer(document, "maximum_source_bytes"),
            maximum_examples=_integer(document, "maximum_examples"),
            lifetime_seconds=_integer(document, "lifetime_seconds"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/sources":
        required = {
            "grant_id", "source_id", "source_family_id", "source_kind",
            "workspace_scope", "sensitivity", "license_id", "input_text",
            "reference_output", "confirmed",
        }
        optional = {
            "evaluation_kind", "evaluation_verifier",
            "evaluation_requirement_id",
        }
        _required_optional(document, required, optional)
        if not _confirmed(document):
            raise PermissionError("dataset source capture requires confirmation")
        reference = document["reference_output"]
        if reference is not None and not isinstance(reference, str):
            raise ValueError("reference_output must be text or null")
        evaluation_kind, evaluation_verifier, evaluation_requirement = (
            _evaluation_metadata(document)
        )
        value = factory.capture_source(
            grant_id=_text(document, "grant_id"),
            source_id=_text(document, "source_id"),
            source_family_id=_text(document, "source_family_id"),
            source_kind=TrainingSourceKind(_text(document, "source_kind")),
            workspace_scope=_text(document, "workspace_scope"),
            sensitivity=TrainingDataSensitivity(_text(document, "sensitivity")),
            license_id=_text(document, "license_id"),
            input_text=_text(document, "input_text"),
            reference_output=reference,
            evaluation_kind=evaluation_kind,
            evaluation_verifier=evaluation_verifier,
            evaluation_requirement_id=evaluation_requirement,
        )
    elif path == "/api/v1/factory/generate":
        _exact(document, {
            "grant_id", "source_id", "teacher_model_ref", "maximum_examples",
            "confirmed",
        })
        value = factory.generate(
            grant_id=_text(document, "grant_id"),
            source_id=_text(document, "source_id"),
            teacher_model_ref=_text(document, "teacher_model_ref"),
            maximum_examples=_integer(document, "maximum_examples"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/reviews":
        _exact(document, {
            "request_id", "grant_id", "example_id", "accepted", "confirmed",
        })
        accepted = document["accepted"]
        if not isinstance(accepted, bool):
            raise ValueError("accepted must be boolean")
        value = factory.review_example(
            request_id=_text(document, "request_id"),
            grant_id=_text(document, "grant_id"),
            example_id=_text(document, "example_id"), accepted=accepted,
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/seal":
        _exact(document, {
            "dataset_id", "grant_id", "near_duplicate_threshold_ppm",
            "confirmed",
        })
        dataset, report = factory.seal_dataset(
            dataset_id=_text(document, "dataset_id"),
            grant_id=_text(document, "grant_id"),
            near_duplicate_threshold_ppm=_integer(
                document, "near_duplicate_threshold_ppm",
            ),
            confirmed=_confirmed(document),
        )
        handler._json(200, {
            "dataset": None if dataset is None else task_document(dataset),
            "leakage_report": task_document(report),
        })
        return True
    elif path == "/api/v1/factory/capture-grants/revoke":
        _exact(document, {
            "grant_id", "expected_revision", "reason_code", "confirmed",
        })
        value = factory.revoke_capture_grant(
            grant_id=_text(document, "grant_id"),
            expected_revision=_integer(document, "expected_revision"),
            reason_code=_text(document, "reason_code"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/training-approvals":
        _exact(document, {
            "request_id", "proposal_id", "sealed_dataset_id",
            "approved_dataset_license_ids", "approved_dataset_sensitivities",
            "base_model", "recipe", "resources", "environment_sha256",
            "maximum_wall_seconds", "maximum_checkpoint_bytes",
            "maximum_output_bytes", "one_use_job_id", "lifetime_seconds",
            "confirmed",
        })
        value = factory.issue_training_approval(
            request_id=_text(document, "request_id"),
            proposal_id=_text(document, "proposal_id"),
            sealed_dataset_id=_text(document, "sealed_dataset_id"),
            approved_dataset_license_ids=tuple(sorted(
                _strings(document, "approved_dataset_license_ids"),
            )),
            approved_dataset_sensitivities=tuple(sorted(
                _strings(document, "approved_dataset_sensitivities"),
            )),
            base_model=_base_model(_object(document, "base_model")),
            recipe=_recipe(_object(document, "recipe")),
            resources=_resources(_object(document, "resources")),
            environment_sha256=_text(document, "environment_sha256"),
            maximum_wall_seconds=_integer(document, "maximum_wall_seconds"),
            maximum_checkpoint_bytes=_integer(
                document, "maximum_checkpoint_bytes",
            ),
            maximum_output_bytes=_integer(document, "maximum_output_bytes"),
            one_use_job_id=_text(document, "one_use_job_id"),
            lifetime_seconds=_integer(document, "lifetime_seconds"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/training-approvals/revoke":
        _exact(document, {
            "approval_id", "expected_revision", "reason_code", "confirmed",
        })
        value = factory.revoke_training_approval(
            approval_id=_text(document, "approval_id"),
            expected_revision=_integer(document, "expected_revision"),
            reason_code=_text(document, "reason_code"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/training-environments/probe":
        _exact(document, {"confirmed"})
        value = factory.probe_training_environment(
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/training-jobs":
        _exact(document, {"request_id", "approval_id", "confirmed"})
        value = factory.start_training(
            request_id=_text(document, "request_id"),
            approval_id=_text(document, "approval_id"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/evaluation-environments/probe":
        _exact(document, {"confirmed"})
        value = factory.probe_evaluation_environment(
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/evaluation-approvals":
        _exact(document, {
            "request_id", "training_receipt_id", "incumbent_expert_id",
            "incumbent_artifact_sha256", "suite_sha256",
            "evaluator_environment_sha256", "evaluator_script_sha256",
            "policy", "one_use_evaluation_id", "lifetime_seconds", "confirmed",
        })
        value = factory.issue_evaluation_approval(
            request_id=_text(document, "request_id"),
            training_receipt_id=_text(document, "training_receipt_id"),
            incumbent_expert_id=_text(document, "incumbent_expert_id"),
            incumbent_artifact_sha256=_text(
                document, "incumbent_artifact_sha256",
            ),
            suite_sha256=_text(document, "suite_sha256"),
            evaluator_environment_sha256=_text(
                document, "evaluator_environment_sha256",
            ),
            evaluator_script_sha256=_text(document, "evaluator_script_sha256"),
            policy=_evaluation_policy(_object(document, "policy")),
            one_use_evaluation_id=_text(document, "one_use_evaluation_id"),
            lifetime_seconds=_integer(document, "lifetime_seconds"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/evaluations":
        _exact(document, {"approval_id", "confirmed"})
        value = factory.start_evaluation(
            approval_id=_text(document, "approval_id"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/conversion-environments/probe":
        _exact(document, {"confirmed"})
        value = factory.probe_conversion_environment(
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/conversion-approvals":
        _exact(document, {
            "request_id", "evaluation_id", "environment_sha256",
            "base_output_type", "adapter_output_type", "runtime_model_ref",
            "maximum_output_bytes", "maximum_wall_seconds",
            "maximum_ram_bytes", "maximum_cpu_cores",
            "one_use_conversion_id", "lifetime_seconds", "confirmed",
        })
        value = factory.issue_conversion_approval(
            request_id=_text(document, "request_id"),
            evaluation_id=_text(document, "evaluation_id"),
            environment_sha256=_text(document, "environment_sha256"),
            base_output_type=ConversionOutputType(
                _text(document, "base_output_type"),
            ),
            adapter_output_type=ConversionOutputType(
                _text(document, "adapter_output_type"),
            ),
            runtime_model_ref=_text(document, "runtime_model_ref"),
            maximum_output_bytes=_integer(document, "maximum_output_bytes"),
            maximum_wall_seconds=_integer(document, "maximum_wall_seconds"),
            maximum_ram_bytes=_integer(document, "maximum_ram_bytes"),
            maximum_cpu_cores=_integer(document, "maximum_cpu_cores"),
            one_use_conversion_id=_text(document, "one_use_conversion_id"),
            lifetime_seconds=_integer(document, "lifetime_seconds"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/conversions":
        _exact(document, {"approval_id", "confirmed"})
        value = factory.start_conversion(
            approval_id=_text(document, "approval_id"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/packages":
        _exact(document, {
            "release_id", "conversion_id", "package_id", "package_version",
            "expert_id", "declared_capabilities", "required_verifier_ids",
            "tokenizer_path", "chat_template_path", "confirmed",
        })
        value = factory.package_specialist(
            release_id=_text(document, "release_id"),
            conversion_id=_text(document, "conversion_id"),
            package_id=_text(document, "package_id"),
            package_version=_text(document, "package_version"),
            expert_id=_text(document, "expert_id"),
            declared_capabilities=_strings(
                document, "declared_capabilities",
            ),
            required_verifier_ids=_strings(
                document, "required_verifier_ids",
            ),
            tokenizer_path=_absolute_path(document, "tokenizer_path"),
            chat_template_path=_absolute_path(document, "chat_template_path"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/canary-approvals":
        _exact(document, {
            "request_id", "package_receipt_id", "suite_path", "verifier_id",
            "maximum_output_tokens", "maximum_wall_seconds",
            "maximum_ram_bytes", "maximum_vram_bytes", "one_use_canary_id",
            "lifetime_seconds", "confirmed",
        })
        value = factory.issue_canary_approval(
            request_id=_text(document, "request_id"),
            package_receipt_id=_text(document, "package_receipt_id"),
            suite_path=_absolute_path(document, "suite_path"),
            verifier_id=_text(document, "verifier_id"),
            maximum_output_tokens=_integer(
                document, "maximum_output_tokens",
            ),
            maximum_wall_seconds=_integer(document, "maximum_wall_seconds"),
            maximum_ram_bytes=_integer(document, "maximum_ram_bytes"),
            maximum_vram_bytes=_integer(document, "maximum_vram_bytes"),
            one_use_canary_id=_text(document, "one_use_canary_id"),
            lifetime_seconds=_integer(document, "lifetime_seconds"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/canaries":
        _exact(document, {"approval_id", "confirmed"})
        value = factory.start_canary(
            approval_id=_text(document, "approval_id"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/activations":
        _exact(document, {"canary_id", "confirmed"})
        value = factory.activate_specialist(
            canary_id=_text(document, "canary_id"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/rollbacks":
        _exact(document, {
            "request_id", "release_id", "target_release_id",
            "expected_lifecycle_revision", "reason_code", "confirmed",
        })
        value = factory.rollback_specialist(
            request_id=_text(document, "request_id"),
            release_id=_text(document, "release_id"),
            target_release_id=_optional_text(document, "target_release_id"),
            expected_lifecycle_revision=_integer(
                document, "expected_lifecycle_revision",
            ),
            reason_code=_text(document, "reason_code"),
            confirmed=_confirmed(document),
        )
    elif path == "/api/v1/factory/retirements":
        _exact(document, {
            "request_id", "release_id", "expected_lifecycle_revision",
            "reason_code", "remove_artifact", "confirmed",
        })
        remove_artifact = document.get("remove_artifact")
        if not isinstance(remove_artifact, bool):
            raise ValueError("remove_artifact must be boolean")
        value = factory.retire_specialist(
            request_id=_text(document, "request_id"),
            release_id=_text(document, "release_id"),
            expected_lifecycle_revision=_integer(
                document, "expected_lifecycle_revision",
            ),
            reason_code=_text(document, "reason_code"),
            remove_artifact=remove_artifact,
            confirmed=_confirmed(document),
        )
    else:
        return False
    handler._json(200, task_document(value))
    return True


def _exact(document: dict, names: set[str]) -> None:
    if set(document) != names:
        raise ValueError("factory request fields must match exactly")


def _required_optional(
    document: dict, required: set[str], optional: set[str],
) -> None:
    fields = set(document)
    if not required <= fields or not fields <= required | optional:
        raise ValueError("factory request fields are invalid")


def _text(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _strings(document: dict, name: str) -> tuple[str, ...]:
    value = document.get(name)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be a nonempty text list")
    return tuple(value)


def _optional_text(document: dict, name: str) -> str | None:
    value = document.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text or null")
    return value


def _optional_evaluation_kind(
    document: dict,
) -> HeldOutEvaluationKind | None:
    value = document.get("evaluation_kind")
    return None if value is None else HeldOutEvaluationKind(
        _text(document, "evaluation_kind"),
    )


def _optional_evaluation_verifier(
    document: dict,
) -> HeldOutVerifierKind | None:
    value = document.get("evaluation_verifier")
    return None if value is None else HeldOutVerifierKind(
        _text(document, "evaluation_verifier"),
    )


def _evaluation_metadata(
    document: dict,
) -> tuple[HeldOutEvaluationKind | None, HeldOutVerifierKind | None, str | None]:
    raw = tuple(document.get(name) for name in (
        "evaluation_kind", "evaluation_verifier", "evaluation_requirement_id",
    ))
    if any(value is not None for value in raw) and any(
        value is None for value in raw
    ):
        raise ValueError("held-out evaluation metadata must be complete")
    return (
        _optional_evaluation_kind(document),
        _optional_evaluation_verifier(document),
        _optional_text(document, "evaluation_requirement_id"),
    )


def _integer(document: dict, name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _confirmed(document: dict) -> bool:
    value = document.get("confirmed")
    if not isinstance(value, bool):
        raise ValueError("confirmed must be boolean")
    return value


def _object(document: dict, name: str) -> dict:
    value = document.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _absolute_path(document: dict, name: str) -> Path:
    value = Path(_text(document, name))
    if not value.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return value


def _number(document: dict, name: str) -> float:
    value = document.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _base_model(document: dict) -> ApprovedBaseModel:
    _exact(document, {
        "repository_id", "revision", "tokenizer_id", "tokenizer_revision",
        "license_id", "files_manifest_sha256",
    })
    return ApprovedBaseModel(
        _text(document, "repository_id"), _text(document, "revision"),
        _text(document, "tokenizer_id"), _text(document, "tokenizer_revision"),
        _text(document, "license_id"), _text(document, "files_manifest_sha256"),
    )


def _recipe(document: dict) -> AdapterTrainingRecipe:
    _exact(document, {
        "recipe_id", "method", "rank", "alpha", "dropout", "target_modules",
        "base_weight_bits", "quantization_type", "double_quantization",
        "compute_dtype", "maximum_sequence_tokens", "epochs", "maximum_steps",
        "per_device_batch_size", "gradient_accumulation_steps",
        "learning_rate", "seed",
    })
    quantization_type = document["quantization_type"]
    if quantization_type is not None and not isinstance(quantization_type, str):
        raise ValueError("quantization_type must be text or null")
    double_quantization = document["double_quantization"]
    if not isinstance(double_quantization, bool):
        raise ValueError("double_quantization must be boolean")
    return AdapterTrainingRecipe(
        _text(document, "recipe_id"),
        AdapterTrainingMethod(_text(document, "method")),
        _integer(document, "rank"), _integer(document, "alpha"),
        _number(document, "dropout"), _strings(document, "target_modules"),
        _integer(document, "base_weight_bits"), quantization_type,
        double_quantization,
        TrainingComputeDtype(_text(document, "compute_dtype")),
        _integer(document, "maximum_sequence_tokens"),
        _number(document, "epochs"), _integer(document, "maximum_steps"),
        _integer(document, "per_device_batch_size"),
        _integer(document, "gradient_accumulation_steps"),
        _number(document, "learning_rate"), _integer(document, "seed"),
    )


def _resources(document: dict) -> TrainingResourceBudget:
    _exact(document, {
        "budget_id", "maximum_cpu_cores", "maximum_ram_bytes",
        "maximum_vram_bytes", "maximum_disk_bytes",
        "maximum_temperature_celsius", "maximum_energy_joules",
        "cgroup_policy_id",
    })
    return TrainingResourceBudget(
        _text(document, "budget_id"), _integer(document, "maximum_cpu_cores"),
        _integer(document, "maximum_ram_bytes"),
        _integer(document, "maximum_vram_bytes"),
        _integer(document, "maximum_disk_bytes"),
        _integer(document, "maximum_temperature_celsius"),
        _integer(document, "maximum_energy_joules"),
        _text(document, "cgroup_policy_id"),
    )


def _evaluation_policy(document: dict):
    _exact(document, {
        "policy_id", "capability_id", "minimum_quality_cases",
        "minimum_quality_ppm", "minimum_improvement_ppm", "confidence_z_ppm",
        "maximum_unrelated_regression_ppm",
        "maximum_p95_latency_microseconds", "maximum_latency_regression_ppm",
        "maximum_peak_ram_bytes", "maximum_peak_vram_bytes",
        "maximum_energy_joules", "maximum_resource_regression_ppm",
        "maximum_adapter_bytes", "maximum_cold_start_microseconds",
        "require_scheduler_compatibility",
    })
    scheduler = document.get("require_scheduler_compatibility")
    if not isinstance(scheduler, bool):
        raise ValueError("require_scheduler_compatibility must be boolean")
    return build_evaluation_policy(
        policy_id=_text(document, "policy_id"),
        capability_id=_text(document, "capability_id"),
        minimum_quality_cases=_integer(document, "minimum_quality_cases"),
        minimum_quality_ppm=_integer(document, "minimum_quality_ppm"),
        minimum_improvement_ppm=_integer(document, "minimum_improvement_ppm"),
        confidence_z_ppm=_integer(document, "confidence_z_ppm"),
        maximum_unrelated_regression_ppm=_integer(
            document, "maximum_unrelated_regression_ppm",
        ),
        maximum_p95_latency_microseconds=_integer(
            document, "maximum_p95_latency_microseconds",
        ),
        maximum_latency_regression_ppm=_integer(
            document, "maximum_latency_regression_ppm",
        ),
        maximum_peak_ram_bytes=_integer(document, "maximum_peak_ram_bytes"),
        maximum_peak_vram_bytes=_integer(document, "maximum_peak_vram_bytes"),
        maximum_energy_joules=_integer(document, "maximum_energy_joules"),
        maximum_resource_regression_ppm=_integer(
            document, "maximum_resource_regression_ppm",
        ),
        maximum_adapter_bytes=_integer(document, "maximum_adapter_bytes"),
        maximum_cold_start_microseconds=_integer(
            document, "maximum_cold_start_microseconds",
        ),
        require_scheduler_compatibility=scheduler,
    )
