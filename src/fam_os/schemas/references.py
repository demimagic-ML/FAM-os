"""Cross-document reference validation after strict per-document decoding."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.applications import ConnectorManifest
from fam_os.core.contracts import ExecutionPlan, TaskRequest, TaskResult
from fam_os.experts import ExpertManifest
from fam_os.memory import MemoryRecordManifest
from fam_os.scheduler.resources import EffectiveResourceBudget, HostInventory
from fam_os.schemas.errors import CrossContractValidationError
from fam_os.verification import VerifierManifest


@dataclass(frozen=True, slots=True)
class ReferenceIssue:
    code: str
    source_id: str
    target_id: str
    safe_message: str


@dataclass(frozen=True, slots=True)
class ContractReferenceSet:
    requests: tuple[TaskRequest, ...] = ()
    plans: tuple[ExecutionPlan, ...] = ()
    results: tuple[TaskResult, ...] = ()
    inventories: tuple[HostInventory, ...] = ()
    budgets: tuple[EffectiveResourceBudget, ...] = ()
    experts: tuple[ExpertManifest, ...] = ()
    verifiers: tuple[VerifierManifest, ...] = ()
    connectors: tuple[ConnectorManifest, ...] = ()
    memory_records: tuple[MemoryRecordManifest, ...] = ()
    known_schema_ids: frozenset[str] = frozenset()


def find_reference_issues(references: ContractReferenceSet) -> tuple[ReferenceIssue, ...]:
    issues: list[ReferenceIssue] = []
    issues.extend(_identity_issues(references))
    issues.extend(_core_issues(references))
    issues.extend(_hardware_issues(references))
    issues.extend(_manifest_issues(references))
    issues.extend(_memory_issues(references))
    return tuple(issues)


def require_valid_references(references: ContractReferenceSet) -> None:
    issues = find_reference_issues(references)
    if issues:
        raise CrossContractValidationError(tuple(issue.code for issue in issues))


def _identity_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    groups = (
        (refs.requests, "request_id", "core.request.duplicate"),
        (refs.plans, "plan_id", "core.plan.duplicate"),
        (refs.inventories, "inventory_id", "hardware.inventory.duplicate"),
        (refs.budgets, "budget_id", "hardware.budget.duplicate"),
        (refs.experts, "expert_id", "expert.manifest.duplicate"),
        (refs.verifiers, "verifier_id", "verifier.manifest.duplicate"),
        (refs.connectors, "connector_id", "connector.manifest.duplicate"),
        (refs.memory_records, "record_id", "memory.record.duplicate"),
    )
    issues: list[ReferenceIssue] = []
    for items, attribute, code in groups:
        values = tuple(getattr(item, attribute) for item in items)
        duplicates = sorted(value for value in set(values) if values.count(value) > 1)
        issues.extend(_issue(code, value, value) for value in duplicates)
    return issues


def _core_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    requests = {item.request_id: item for item in refs.requests}
    plans = {item.plan_id: item for item in refs.plans}
    for plan in refs.plans:
        if plan.request_id not in requests:
            issues.append(_issue("core.plan.request_missing", plan.plan_id, plan.request_id))
    for result in refs.results:
        if result.request_id not in requests:
            issues.append(_issue("core.result.request_missing", result.request_id, result.request_id))
        if result.plan_id is None:
            continue
        plan = plans.get(result.plan_id)
        if plan is None:
            issues.append(_issue("core.result.plan_missing", result.request_id, result.plan_id))
        elif plan.request_id != result.request_id:
            issues.append(_issue("core.result.plan_request_mismatch", result.request_id, plan.request_id))
    return issues


def _hardware_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    inventories = {item.inventory_id: item for item in refs.inventories}
    for budget in refs.budgets:
        inventory = inventories.get(budget.inventory_id)
        if inventory is None:
            issues.append(_issue("hardware.budget.inventory_missing", budget.budget_id, budget.inventory_id))
            continue
        accelerator_ids = {item.device_id for item in inventory.accelerators}
        storage = {item.storage_id: item for item in inventory.storage}
        for item in budget.accelerators:
            if item.device_id not in accelerator_ids:
                issues.append(_issue("hardware.budget.accelerator_missing", budget.budget_id, item.device_id))
        for item in budget.storage:
            inventory_storage = storage.get(item.storage_id)
            if inventory_storage is None:
                issues.append(_issue("hardware.budget.storage_missing", budget.budget_id, item.storage_id))
            elif item.scheduler_cache_limit_bytes and not inventory_storage.cache_eligible:
                issues.append(_issue("hardware.budget.storage_not_cache_eligible", budget.budget_id, item.storage_id))
    return issues


def _manifest_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    verifier_ids = {item.verifier_id for item in refs.verifiers}
    known_schemas = refs.known_schema_ids
    for expert in refs.experts:
        for verifier_id in expert.required_verifier_ids:
            if verifier_id not in verifier_ids:
                issues.append(_issue("expert.verifier_missing", expert.expert_id, verifier_id))
    for verifier in refs.verifiers:
        schema_ids = (*verifier.candidate_schema_ids, verifier.evidence_schema_id)
        issues.extend(_schema_issues("verifier.schema_missing", verifier.verifier_id, schema_ids, known_schemas))
    for connector in refs.connectors:
        for capability in connector.capabilities:
            schema_ids = (capability.input_schema_id, capability.output_schema_id)
            issues.extend(_schema_issues("connector.schema_missing", connector.connector_id, schema_ids, known_schemas))
    return issues


def _memory_issues(refs: ContractReferenceSet) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    record_ids = {item.record_id for item in refs.memory_records}
    for record in refs.memory_records:
        if record.content_schema_id not in refs.known_schema_ids:
            issues.append(
                _issue("memory.content_schema_missing", record.record_id, record.content_schema_id)
            )
        for parent_id in record.provenance.parent_record_ids:
            if parent_id not in record_ids:
                issues.append(_issue("memory.parent_missing", record.record_id, parent_id))
    return issues


def _schema_issues(
    code: str, source_id: str, schema_ids: tuple[str, ...], known: frozenset[str]
) -> list[ReferenceIssue]:
    return [_issue(code, source_id, schema_id) for schema_id in schema_ids if schema_id not in known]


def _issue(code: str, source_id: str, target_id: str) -> ReferenceIssue:
    return ReferenceIssue(code, source_id, target_id, "A referenced contract object is unavailable.")
