"""Core admission and postcondition policy for isolated project dependencies."""

from datetime import datetime
from typing import Protocol

from fam_os.core.engineering.authority import EngineeringOperation, EngineeringTaskEnvelope
from fam_os.core.engineering.dependencies import (
    DependencyFindingSeverity, DependencyResolutionReceipt,
    DependencyResolutionRequest, DependencyResolutionStatus,
)
from fam_os.core.engineering.grants import EngineeringAuthorityGrant


class LicensePolicyEvaluator(Protocol):
    def require_allowed(self, expression: str, allowed: tuple[str, ...]) -> None: ...


class DependencyAdmissionPolicy:
    def __init__(self, licenses: LicensePolicyEvaluator) -> None:
        self._licenses = licenses

    def authorize(
        self,
        request: DependencyResolutionRequest,
        task: EngineeringTaskEnvelope,
        grant: EngineeringAuthorityGrant,
        *,
        instant: datetime,
    ) -> None:
        if request.task_id != task.task_id or task.grant_id != grant.grant_id:
            raise PermissionError("dependency request task or grant is mismatched")
        if not grant.active_at(instant) or not task.created_at <= instant < task.expires_at:
            raise PermissionError("dependency task authority is inactive")
        if EngineeringOperation.MANAGE_DEPENDENCY not in task.permitted_operations:
            raise PermissionError("dependency operation is outside the task envelope")
        if request.ecosystem not in task.toolchains:
            raise PermissionError("dependency ecosystem is outside task toolchains")
        if not set(request.registry_urls).issubset(task.package_registries):
            raise PermissionError("dependency registry is outside task scope")
        if not set(request.network_hosts).issubset(task.network_hosts):
            raise PermissionError("dependency network host is outside task scope")
        if request.budget.maximum_wall_seconds > min(
            task.max_wall_seconds, grant.resource_impact.max_wall_seconds,
        ):
            raise PermissionError("dependency wall-time budget exceeds grant")
        if request.budget.maximum_download_bytes > grant.resource_impact.max_network_bytes:
            raise PermissionError("dependency network budget exceeds grant")
        for expression in request.allowed_license_expressions:
            self._licenses.require_allowed(
                expression, request.allowed_license_expressions,
            )

    def validate_receipt(
        self,
        request: DependencyResolutionRequest,
        receipt: DependencyResolutionReceipt,
    ) -> None:
        if (
            receipt.request_id != request.request_id
            or receipt.task_id != request.task_id
            or receipt.candidate_id != request.candidate_id
            or receipt.environment_path != request.environment_path
        ):
            raise ValueError("dependency receipt identity is mismatched")
        if receipt.downloaded_bytes > request.budget.maximum_download_bytes:
            raise ValueError("dependency download budget was exceeded")
        if receipt.installed_bytes > request.budget.maximum_installed_bytes:
            raise ValueError("dependency installed-size budget was exceeded")
        if len(receipt.components) > request.budget.maximum_packages:
            raise ValueError("dependency package-count budget was exceeded")
        if not set(receipt.network_destinations).issubset(request.network_hosts):
            raise ValueError("dependency receipt contains an unapproved destination")
        for component in receipt.components:
            self._licenses.require_allowed(
                component.license_expression,
                request.allowed_license_expressions,
            )
        direct_names = {item.name for item in receipt.components if item.direct}
        if direct_names != set(request.requested_packages):
            raise ValueError("dependency receipt direct packages differ from approved names")
        severe = {
            DependencyFindingSeverity.HIGH,
            DependencyFindingSeverity.CRITICAL,
        }
        if receipt.status is DependencyResolutionStatus.ACCEPTED and any(
            finding.severity in severe for finding in receipt.vulnerability_findings
        ):
            raise ValueError("accepted dependency receipt contains severe vulnerability")
