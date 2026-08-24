"""Real network-isolated paired NVIDIA specialist evaluator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.training.environment_probe import NvidiaQloraEnvironmentProbe
from fam_os.adapters.training.isolated_evaluation_command import (
    build_isolated_evaluation_command,
)
from fam_os.expert_factory import (
    EvaluationCaseKind,
    ExpertComparisonDecision,
    FactoryEvaluationApproval,
    TrainingBackendEnvironment,
    build_evaluation_report,
    build_held_out_access_receipt,
    build_paired_measurement,
    decide_comparison,
)
from fam_os.product.factory_evaluation_workspace import FactoryEvaluationWorkspace
from fam_os.product.factory_training_workspace import model_files_manifest_sha256
from fam_os.product.candidate_scheduler_compatibility import (
    CandidateSchedulerCompatibilityProbe,
)


class NvidiaSpecialistEvaluator:
    def __init__(
        self, *, repositories, environment_probe: NvidiaQloraEnvironmentProbe,
        workspace: FactoryEvaluationWorkspace, environment_directory: Path,
        worker_script: Path, model_directory: Path, training_workspace_root: Path,
        suite_path: Path, signer_key_id: str, signing_key: Ed25519PrivateKey,
        scheduler_probe: CandidateSchedulerCompatibilityProbe,
        now=None,
    ) -> None:
        self._repositories = repositories
        self._environment_probe = environment_probe
        self._workspace = workspace
        self._environment_directory = environment_directory
        self._worker_script = worker_script
        self._model_directory = model_directory
        self._training_workspace_root = training_workspace_root
        self._suite_path = suite_path
        self._signer_key_id = signer_key_id
        self._signing_key = signing_key
        self._scheduler_probe = scheduler_probe
        self._now = now or (lambda: datetime.now(UTC))

    def probe(self) -> TrainingBackendEnvironment:
        environment = self._environment_probe.probe()
        self._repositories.training_jobs.add_environment(environment)
        return environment

    def run(
        self, *, approval_id: str, confirmed: bool,
    ) -> ExpertComparisonDecision:
        if not confirmed:
            raise PermissionError("held-out evaluation requires confirmation")
        approval = self._repositories.factory_evaluations.approval(approval_id)
        if approval is None:
            raise KeyError("evaluation approval is unavailable")
        existing = self._repositories.factory_evaluations.decision(
            approval.one_use_evaluation_id,
        )
        if existing is not None:
            return existing
        environment = self.probe()
        if environment.manifest_sha256 != approval.evaluator_environment_sha256:
            raise PermissionError("evaluator environment changed after approval")
        if _file_sha256(self._worker_script) != approval.evaluator_script_sha256:
            raise PermissionError("evaluator script changed after approval")
        if model_files_manifest_sha256(self._model_directory) != (
            approval.incumbent_artifact_sha256
        ):
            raise PermissionError("incumbent artifact changed after approval")
        if _file_sha256(self._suite_path) != approval.suite_sha256:
            raise PermissionError("evaluation suite changed after approval")
        terminal = next(
            item for item in self._repositories.training_jobs.terminals()
            if item.receipt_id == approval.training_receipt_id
        )
        adapter = self._training_workspace_root / terminal.job_id / "output/adapter"
        if _directory_sha256(adapter) != approval.adapter_sha256 or _file_sha256(
            adapter / "adapter_config.json",
        ) != approval.adapter_config_sha256:
            raise PermissionError("candidate adapter changed after approval")
        held_out = next(
            item for item in self._repositories.sealed_datasets.blobs(
                approval.sealed_dataset_id,
            ) if item.blob_id == approval.held_out_blob_id
        )
        now = self._now()
        self._repositories.factory_evaluations.claim(
            approval.approval_id, approval.one_use_evaluation_id,
            approval.revision, now,
        )
        self._repositories.factory_evaluations.mark_running(
            approval.one_use_evaluation_id, now,
        )
        plaintext_bytes = 0
        with self._workspace.materialize(
            approval=approval, held_out=held_out,
        ) as prepared:
            plaintext_bytes = prepared.plaintext_bytes
            suite_copy = prepared.input_directory / "suite.jsonl"
            _write_private_new(suite_copy, self._suite_path.read_bytes())
            config = prepared.input_directory / "config.json"
            _write_private_new(config, _config(
                approval, prepared.held_out_path, suite_copy, adapter,
            ))
            command = build_isolated_evaluation_command(
                approval=approval, environment=self._environment_directory,
                worker_script=self._worker_script, model=self._model_directory,
                adapter=adapter, input_directory=prepared.input_directory,
                output_directory=prepared.output_directory,
            )
            started = self._now()
            result = subprocess.run(
                command, check=False, capture_output=True, timeout=900,
            )
            finished = self._now()
            if result.returncode != 0:
                raise RuntimeError("isolated evaluator failed")
            worker = _worker_result(prepared.output_directory)
        access = build_held_out_access_receipt(
            receipt_id=f"held-out-access-{approval.one_use_evaluation_id}",
            approval_id=approval.approval_id,
            evaluation_id=approval.one_use_evaluation_id,
            dataset_id=approval.sealed_dataset_id,
            held_out_blob_id=approval.held_out_blob_id,
            held_out_blob_sha256=approval.held_out_blob_sha256,
            evaluator_environment_sha256=approval.evaluator_environment_sha256,
            plaintext_bytes=plaintext_bytes, plaintext_discarded=True,
            accessed_at=finished,
        )
        self._repositories.factory_evaluations.record_access(access)
        measurements = _measurements(approval, worker, finished)
        adapter_bytes = _directory_bytes(adapter)
        report = build_evaluation_report(
            report_id=f"evaluation-report-{approval.one_use_evaluation_id}",
            approval_id=approval.approval_id,
            evaluation_id=approval.one_use_evaluation_id,
            policy=approval.policy,
            evaluator_environment_sha256=approval.evaluator_environment_sha256,
            evaluator_script_sha256=approval.evaluator_script_sha256,
            held_out_access_receipt_sha256=access.receipt_sha256,
            network_denied="--unshare-all" in command and "--share-net" not in command,
            measurements=measurements,
            candidate_adapter_bytes=adapter_bytes,
            candidate_cold_start_microseconds=_integer(
                worker, "candidate_cold_start_microseconds",
            ),
            scheduler_compatible=self._scheduler_probe.compatible(
                approval=approval, measurements=measurements,
                base_artifact_bytes=_directory_bytes(self._model_directory),
                adapter_bytes=adapter_bytes,
            ),
            started_at=started, finished_at=finished,
        )
        decision = decide_comparison(
            decision_id=f"evaluation-decision-{approval.one_use_evaluation_id}",
            approval=approval, report=report, decided_at=finished,
            signer_key_id=self._signer_key_id, signing_key=self._signing_key,
        )
        self._repositories.factory_evaluations.complete(
            measurements, report, decision,
        )
        return decision


def _config(
    approval: FactoryEvaluationApproval, held_out: Path, suite: Path,
    adapter: Path,
) -> bytes:
    document = {
        "adapter_config_sha256": approval.adapter_config_sha256,
        "adapter_directory": "/adapter",
        "adapter_sha256": approval.adapter_sha256,
        "base_model_directory": "/model",
        "base_model_sha256": approval.incumbent_artifact_sha256,
        "held_out_path": "/input/held-out.jsonl",
        "held_out_sha256": _file_sha256(held_out),
        "maximum_new_tokens": 512, "seed": 42,
        "suite_path": "/input/suite.jsonl",
        "suite_sha256": _file_sha256(suite),
    }
    if _directory_sha256(adapter) != approval.adapter_sha256:
        raise PermissionError("candidate adapter changed while configuring evaluation")
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _measurements(
    approval: FactoryEvaluationApproval, worker: dict, measured_at: datetime,
):
    raw = worker.get("measurements")
    if worker.get("status") != "completed" or not isinstance(raw, list) or not raw:
        raise RuntimeError("evaluator returned no complete measurements")
    values = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise RuntimeError("evaluator measurement is invalid")
        baseline = _mapping(item, "baseline")
        candidate = _mapping(item, "candidate")
        values.append(build_paired_measurement(
            measurement_id=f"evaluation-measurement-{approval.one_use_evaluation_id}-{index}",
            evaluation_id=approval.one_use_evaluation_id,
            case_id=_text(item, "case_id"),
            kind=EvaluationCaseKind(_text(item, "kind")),
            requirement_id=_text(item, "requirement_id"),
            input_sha256=_sha(item, "input_sha256"),
            expected_sha256=_sha(item, "expected_sha256"),
            baseline_output_sha256=_sha(baseline, "output_sha256"),
            candidate_output_sha256=_sha(candidate, "output_sha256"),
            baseline_passed=_boolean(baseline, "passed"),
            candidate_passed=_boolean(candidate, "passed"),
            baseline_latency_microseconds=_integer(baseline, "latency_microseconds"),
            candidate_latency_microseconds=_integer(candidate, "latency_microseconds"),
            baseline_peak_ram_bytes=_integer(baseline, "peak_ram_bytes"),
            candidate_peak_ram_bytes=_integer(candidate, "peak_ram_bytes"),
            baseline_peak_vram_bytes=_integer(baseline, "peak_vram_bytes"),
            candidate_peak_vram_bytes=_integer(candidate, "peak_vram_bytes"),
            baseline_energy_millijoules=_integer(baseline, "energy_millijoules"),
            candidate_energy_millijoules=_integer(candidate, "energy_millijoules"),
            measured_at=measured_at,
        ))
    return tuple(values)


def _worker_result(output: Path) -> dict:
    path = output / "evaluation-result.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise RuntimeError("evaluator result artifact is unavailable")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("evaluator result artifact is invalid")
    return value


def _mapping(document: dict, name: str) -> dict:
    value = document.get(name)
    if not isinstance(value, dict):
        raise RuntimeError(f"evaluator {name} is invalid")
    return value


def _text(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"evaluator {name} is invalid")
    return value


def _sha(document: dict, name: str) -> str:
    value = _text(document, name)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RuntimeError(f"evaluator {name} is not SHA-256")
    return value


def _integer(document: dict, name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError(f"evaluator {name} is invalid")
    return value


def _boolean(document: dict, name: str) -> bool:
    value = document.get(name)
    if not isinstance(value, bool):
        raise RuntimeError(f"evaluator {name} is invalid")
    return value


def _write_private_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _directory_sha256(path: Path) -> str:
    records = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("evaluation artifact contains symlinks")
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), _file_sha256(item)))
    if not records:
        raise ValueError("evaluation artifact directory is empty")
    return hashlib.sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
