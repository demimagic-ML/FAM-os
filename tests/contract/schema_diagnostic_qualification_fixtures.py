"""Representative complete diagnostic qualification schema values."""

from datetime import datetime, timezone

from fam_os.core.engineering import (
    RuntimeDiagnosticKind,
    RuntimeDiagnosticQualification,
    RuntimeDiagnosticQualificationMatrix,
    ToolQualificationStatus,
)


NOW = datetime(2026, 7, 19, 14, 0, tzinfo=timezone.utc)


def diagnostic_qualification_schema_values() -> tuple[object, ...]:
    qualifications = tuple(
        RuntimeDiagnosticQualification(
            f"qualification-{kind.value}", kind,
            f"engineering.c.{kind.value}", "1.0.0", "physical-tool-1",
            f"positive-{kind.value}", f"negative-{kind.value}",
            ToolQualificationStatus.PASSED, True, NOW, "release-1",
        )
        for kind in RuntimeDiagnosticKind
    )
    matrix = RuntimeDiagnosticQualificationMatrix(
        "diagnostic-matrix-1", qualifications,
        ("compat-cpu-16gb", "full-reference-workstation"),
        "release-1", NOW,
    )
    return qualifications[0], matrix
