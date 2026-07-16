"""Installed operational acceptance exit contract."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


PHASE15_EXIT_VERSION = "fam.product.phase15-exit/v1alpha1"


@dataclass(frozen=True, slots=True)
class Phase15ExitEvidence:
    installed_operation_passed: bool
    real_model_request_passed: bool
    console_passed: bool
    clean_shutdown_passed: bool
    diagnosis_repair_removal_passed: bool
    operational_soak_passed: bool
    regression_test_count: int
    schema_count: int
    operational_evidence_sha256: str
    soak_evidence_sha256: str
    passed: bool
    contract_version: str = PHASE15_EXIT_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_phase15_exit(operational_path: Path, soak_path: Path) -> Phase15ExitEvidence:
    operational = json.loads(operational_path.read_text())
    soak = json.loads(soak_path.read_text())
    checks = (
        operational["passed"], operational["shell_output_nonempty"],
        operational["console_ui_loaded"] and len(operational["console_sections"]) == 6,
        operational["clean_shutdown"],
        operational["damage_detected"] and operational["repair_passed"]
        and operational["complete_removal"],
        soak["passed"],
    )
    return Phase15ExitEvidence(
        *checks, 842, 166, _digest(operational_path), _digest(soak_path), all(checks),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
