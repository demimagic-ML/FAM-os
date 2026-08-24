"""Fail-closed positive/negative qualification for engineering toolchains."""

from datetime import datetime

from fam_os.core.engineering.execution import (
    EngineeringEcosystem, EngineeringToolReceipt, LanguageToolQualification,
    ToolQualificationStatus,
)


class PolyglotQualificationService:
    def qualify(
        self,
        qualification_id: str,
        ecosystem: EngineeringEcosystem,
        tool_name: str,
        tool_version: str,
        positive: EngineeringToolReceipt,
        negative: EngineeringToolReceipt,
        *,
        qualified_at: datetime,
        installed_release_id: str | None,
    ) -> LanguageToolQualification:
        if positive.recipe_id != negative.recipe_id:
            raise ValueError("positive and negative fixtures must use one recipe")
        if positive.status is not ToolQualificationStatus.PASSED:
            raise ValueError("positive toolchain fixture did not pass")
        if negative.status is not ToolQualificationStatus.FAILED:
            raise ValueError("negative toolchain fixture did not fail as expected")
        if positive.candidate_id == negative.candidate_id:
            raise ValueError("qualification fixtures require isolated candidates")
        required_isolation = {
            "bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits",
        }
        for receipt in (positive, negative):
            if not required_isolation.issubset(receipt.isolation_evidence_ids):
                raise ValueError("toolchain fixture lacks required containment evidence")
            if receipt.network_destinations:
                raise ValueError("offline toolchain fixture unexpectedly used network")
        return LanguageToolQualification(
            qualification_id, ecosystem, tool_name, tool_version,
            positive.receipt_id, negative.receipt_id,
            ToolQualificationStatus.PASSED, qualified_at, installed_release_id,
        )
