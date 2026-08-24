"""Fail-closed physical and installed runtime-diagnostic qualification."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.core.engineering._validation import aware, text, texts
from fam_os.core.engineering.diagnostics import RuntimeDiagnosticKind
from fam_os.core.engineering.execution import ToolQualificationStatus
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticQualification:
    qualification_id: str
    kind: RuntimeDiagnosticKind
    signed_recipe_id: str
    signed_recipe_version: str
    tool_version: str
    positive_receipt_id: str
    negative_receipt_id: str
    status: ToolQualificationStatus
    physically_executed: bool
    qualified_at: datetime
    installed_release_id: str | None = None
    diagnostic: str = ""
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in (
            "qualification_id", "signed_recipe_id", "signed_recipe_version",
            "tool_version", "positive_receipt_id", "negative_receipt_id",
        ):
            text(getattr(self, name), name)
        aware(self.qualified_at, "qualified_at")
        if self.installed_release_id is not None:
            text(self.installed_release_id, "installed_release_id")
        if self.status is ToolQualificationStatus.PASSED and not self.physically_executed:
            raise ValueError("passing diagnostic qualification requires physical execution")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("runtime diagnostic qualification version is unsupported")


@dataclass(frozen=True, slots=True)
class RuntimeDiagnosticQualificationMatrix:
    matrix_id: str
    qualifications: tuple[RuntimeDiagnosticQualification, ...]
    required_profile_ids: tuple[str, ...]
    installed_release_id: str | None
    qualified_at: datetime
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.matrix_id, "matrix_id")
        texts(self.required_profile_ids, "required_profile_ids")
        aware(self.qualified_at, "qualified_at")
        if self.installed_release_id is not None:
            text(self.installed_release_id, "installed_release_id")
        kinds = tuple(item.kind for item in self.qualifications)
        if set(kinds) != set(RuntimeDiagnosticKind) or len(kinds) != len(set(kinds)):
            raise ValueError("diagnostic qualification matrix requires every kind exactly once")
        if any(item.status is not ToolQualificationStatus.PASSED for item in self.qualifications):
            raise ValueError("diagnostic qualification matrix cannot pass with failed tools")
        if any(not item.physically_executed for item in self.qualifications):
            raise ValueError("diagnostic qualification matrix requires physical execution")
        if self.installed_release_id is not None and any(
            item.installed_release_id != self.installed_release_id
            for item in self.qualifications
        ):
            raise ValueError("installed diagnostic qualifications must bind one release")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("runtime diagnostic matrix version is unsupported")
