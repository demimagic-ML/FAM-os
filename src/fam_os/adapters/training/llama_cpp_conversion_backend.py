"""One-use, network-denied llama.cpp conversion backend."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from fam_os.adapters.training.conversion_environment import (
    LlamaCppConversionEnvironmentProbe,
)
from fam_os.adapters.training.isolated_conversion_command import (
    build_isolated_conversion_command,
)
from fam_os.expert_factory import (
    ConversionStatus,
    FactoryConversionReceipt,
    build_conversion_receipt,
)
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.product.factory_conversion_workspace import FactoryConversionWorkspace
from fam_os.product.factory_training_workspace import model_files_manifest_sha256


class LlamaCppConversionBackend:
    def __init__(
        self, *, repositories: CoreRepositorySet,
        environment_probe: LlamaCppConversionEnvironmentProbe,
        environment_directory: Path, worker_script: Path,
        llama_cpp_directory: Path, model_directory: Path,
        training_workspace_root: Path, workspace: FactoryConversionWorkspace,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repositories = repositories
        self._environment_probe = environment_probe
        self._environment_directory = environment_directory
        self._worker_script = worker_script
        self._llama_cpp_directory = llama_cpp_directory
        self._model_directory = model_directory
        self._training_workspace_root = training_workspace_root
        self._workspace = workspace
        self._now = now or (lambda: datetime.now(UTC))

    def run(
        self, *, approval_id: str, confirmed: bool,
    ) -> FactoryConversionReceipt:
        if not confirmed:
            raise PermissionError("runtime conversion requires confirmation")
        approval = self._repositories.factory_conversions.approval(approval_id)
        if approval is None:
            raise KeyError("conversion approval is unavailable")
        existing = self._repositories.factory_conversions.receipt(
            approval.one_use_conversion_id,
        )
        if existing is not None:
            return existing
        now = self._now()
        if not approval.active or approval.expires_at <= now:
            raise PermissionError("conversion approval is inactive or expired")
        decision = self._repositories.factory_evaluations.decision(
            approval.evaluation_id,
        )
        if (
            decision is None
            or not decision.promotable
            or decision.decision_id != approval.comparison_decision_id
            or decision.decision_sha256 != approval.comparison_decision_sha256
        ):
            raise PermissionError("signed promotable comparison changed")
        evaluation = self._repositories.factory_evaluations.approval(
            decision.approval_id,
        )
        if evaluation is None:
            raise RuntimeError("evaluation lineage is unavailable")
        terminal = next((
            item for item in self._repositories.training_jobs.terminals()
            if item.receipt_id == evaluation.training_receipt_id
        ), None)
        if terminal is None:
            raise RuntimeError("training receipt is unavailable")
        adapter = (
            self._training_workspace_root / terminal.job_id / "output/adapter"
        ).absolute()
        if _directory_sha256(adapter) != approval.adapter_sha256:
            raise PermissionError("approved adapter changed before conversion")
        if model_files_manifest_sha256(self._model_directory) != (
            approval.base_model_sha256
        ):
            raise PermissionError("approved base model changed before conversion")
        environment = self._environment_probe.probe()
        if environment.manifest_sha256 != approval.environment_sha256:
            raise PermissionError("conversion environment changed after approval")
        prepared = self._workspace.prepare(approval)
        command = build_isolated_conversion_command(
            approval=approval,
            environment=self._environment_directory.absolute(),
            worker_script=self._worker_script.absolute(),
            llama_cpp=self._llama_cpp_directory.absolute(),
            model=self._model_directory.absolute(), adapter=adapter,
            input_directory=prepared.input_directory.absolute(),
            output_directory=prepared.output_directory.absolute(),
        )
        self._repositories.factory_conversions.claim(
            approval.approval_id, approval.one_use_conversion_id,
            approval.revision, now,
        )
        receipt = self._execute(
            approval, prepared.output_directory, command, now,
        )
        self._repositories.factory_conversions.record_receipt(receipt)
        return receipt

    def _execute(
        self, approval: object, output: Path, command: tuple[str, ...],
        started: datetime,
    ) -> FactoryConversionReceipt:
        from fam_os.expert_factory import FactoryConversionApproval

        if not isinstance(approval, FactoryConversionApproval):
            raise TypeError("conversion approval is invalid")
        stdout_path, stderr_path = output / "stdout.log", output / "stderr.log"
        unit = f"fam-conversion-{approval.one_use_conversion_id}.scope"
        stop_reason: str | None = None
        exit_code = 1
        try:
            with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
                while process.poll() is None:
                    time.sleep(0.5)
                    if _directory_bytes(output) > approval.maximum_output_bytes:
                        stop_reason = "conversion.output_exceeded"
                        _stop_unit(unit, process)
                        break
                exit_code = process.wait(timeout=30)
        except (OSError, subprocess.SubprocessError):
            stop_reason = "conversion.worker_launch_failed"
        finished = self._now()
        worker = _worker_result(output)
        completed = (
            stop_reason is None
            and exit_code == 0
            and worker.get("status") == "completed"
            and _validate_outputs(output, worker, approval.maximum_output_bytes)
        )
        if not completed:
            _discard_outputs(output)
        reason = (
            "conversion.completed" if completed else stop_reason
            or _safe_failure_reason(worker)
        )
        receipt = build_conversion_receipt(
            receipt_id=f"conversion-receipt-{approval.one_use_conversion_id}",
            approval_id=approval.approval_id,
            conversion_id=approval.one_use_conversion_id,
            comparison_decision_sha256=approval.comparison_decision_sha256,
            environment_sha256=approval.environment_sha256,
            status=(
                ConversionStatus.COMPLETED if completed
                else ConversionStatus.FAILED
            ),
            reason_code=reason,
            base_gguf_sha256=_sha_value(worker, "base_gguf_sha256") if completed else None,
            base_gguf_bytes=_integer(worker, "base_gguf_bytes") if completed else 0,
            adapter_gguf_sha256=(
                _sha_value(worker, "adapter_gguf_sha256") if completed else None
            ),
            adapter_gguf_bytes=(
                _integer(worker, "adapter_gguf_bytes") if completed else 0
            ),
            modelfile_sha256=(
                _sha_value(worker, "modelfile_sha256") if completed else None
            ),
            runtime_model_ref=approval.runtime_model_ref if completed else None,
            network_denied=(
                "--unshare-all" in command and "--share-net" not in command
            ),
            started_at=started, finished_at=finished,
        )
        return receipt


def _worker_result(output: Path) -> dict[str, object]:
    path = output / "worker-result.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024:
        return {}
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _validate_outputs(
    output: Path, worker: dict[str, object], maximum_bytes: int,
) -> bool:
    expected = {
        "adapter_gguf_bytes", "adapter_gguf_sha256", "base_gguf_bytes",
        "base_gguf_sha256", "modelfile_sha256", "reason_code",
        "runtime_model_ref", "status",
    }
    if set(worker) != expected or _directory_bytes(output) > maximum_bytes:
        return False
    paths = {
        "base_gguf": output / "base.gguf",
        "adapter_gguf": output / "adapter.gguf",
        "modelfile": output / "Modelfile",
    }
    if any(not path.is_file() or path.is_symlink() for path in paths.values()):
        return False
    try:
        return (
            _file_sha256(paths["base_gguf"])
            == _sha_value(worker, "base_gguf_sha256")
            and paths["base_gguf"].stat().st_size
            == _integer(worker, "base_gguf_bytes")
            and _file_sha256(paths["adapter_gguf"])
            == _sha_value(worker, "adapter_gguf_sha256")
            and paths["adapter_gguf"].stat().st_size
            == _integer(worker, "adapter_gguf_bytes")
            and _file_sha256(paths["modelfile"])
            == _sha_value(worker, "modelfile_sha256")
        )
    except (OSError, RuntimeError):
        return False


def _safe_failure_reason(worker: dict[str, object]) -> str:
    value = worker.get("reason_code")
    return (
        value if value in {"conversion.worker_failed"}
        else "conversion.worker_failed"
    )


def _sha_value(document: dict[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise RuntimeError(f"conversion worker {name} is invalid")
    return value


def _integer(document: dict[str, object], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RuntimeError(f"conversion worker {name} is invalid")
    return value


def _directory_sha256(path: Path) -> str:
    if not path.is_dir() or path.is_symlink():
        raise ValueError("conversion adapter directory is invalid")
    records = []
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("conversion adapter contains symlinks")
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), _file_sha256(item)))
    if not records:
        raise ValueError("conversion adapter directory is empty")
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode(),
    ).hexdigest()


def _directory_bytes(path: Path) -> int:
    return sum(
        item.stat().st_size for item in path.rglob("*")
        if item.is_file() and not item.is_symlink()
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discard_outputs(output: Path) -> None:
    for name in ("base.gguf", "adapter.gguf", "Modelfile"):
        (output / name).unlink(missing_ok=True)


def _stop_unit(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ("systemctl", "--user", "kill", "--signal=TERM", unit),
        check=False, capture_output=True, timeout=10,
    )
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
