"""One bounded verification-driven repair inside the natural candidate loop."""

from dataclasses import dataclass

from fam_os.core.engineering import (
    CandidateEditStatus, CandidateGenerationStatus,
    CandidateVerificationStatus, bind_generated_candidate_plan,
)
from fam_os.core.engineering.diagnostic_redaction import (
    sanitize_diagnostic_feedback,
)
from fam_os.product.natural_engineering_incidents import (
    NaturalEngineeringIncidentCoordinator,
)


@dataclass(frozen=True, slots=True)
class NaturalEngineeringRepairResult:
    generation: object | None
    edits: tuple
    verifications: tuple
    documentation: tuple
    incident: object | None
    passed: bool
    failure_code: str | None


class NaturalEngineeringRepairCoordinator:
    def __init__(self, loop, context_reader, generation) -> None:
        self._loop = loop
        self._context_reader = context_reader
        self._generation = generation
        self._incidents = NaturalEngineeringIncidentCoordinator(loop)

    def attempt(
        self, owner_id, definition, preparation, initial_verifications,
        preferred_paths, *, session_id, principal_id, verify,
        before_verify=None,
    ) -> NaturalEngineeringRepairResult:
        task = definition.task
        evidence_ids = tuple(
            item.verification_id for item in initial_verifications
        )
        incident = self._loop.record_incident(
            owner_id, task.task_id, "signed_candidate_verification_failed",
            evidence_ids,
        )
        current = self._loop.current_candidate(owner_id, task.task_id)
        context = self._context_reader.read(
            current, task.intent, preferred_paths,
        )
        generation_id = f"generation-{task.task_id}-repair-1"
        budget = self._loop.remaining_budget(owner_id, task.task_id)
        record = self._generation.generate(
            definition, preparation, context, generation_id=generation_id,
            session_id=session_id, principal_id=principal_id,
            available_tokens=budget["tokens"],
            available_wall_seconds=budget["wall_seconds"],
            repair_feedback=_feedback(initial_verifications),
            binding_candidate=current,
        )
        self._loop.record_generation_budget(owner_id, task.task_id, record)
        if record.status is not CandidateGenerationStatus.PLAN_VALIDATED:
            return NaturalEngineeringRepairResult(
                record, (), (), (), incident, False,
                record.failure_code or "repair_generation_failed",
            )
        if incident is not None:
            incident = self._incidents.propose_repair(
                owner_id, incident, generation_id, evidence_ids,
            )
        budget = self._loop.remaining_budget(owner_id, task.task_id)
        try:
            bound = bind_generated_candidate_plan(
                task.task_id, current, record.plan,
                maximum_operations=min(task.max_changed_files, budget["files"]),
                maximum_content_bytes=min(
                    task.max_changed_bytes, budget["storage_bytes"],
                ),
            )
            edits = tuple(
                self._loop.edit_candidate(
                    owner_id, task.task_id,
                    edit_id=f"edit-{item.operation.operation_id}",
                    session_id=session_id, principal_id=principal_id,
                    operation=item.operation, artifact=item.artifact,
                    content=item.content,
                )
                for item in bound
            )
        except (PermissionError, RuntimeError, ValueError):
            return NaturalEngineeringRepairResult(
                record, (), (), (), incident, False,
                "repair_candidate_edit_failed",
            )
        if any(item.status is not CandidateEditStatus.APPLIED for item in edits):
            return NaturalEngineeringRepairResult(
                record, edits, (), (), incident, False,
                "repair_candidate_edit_postcondition_failed",
            )
        if incident is not None:
            incident = self._incidents.record_remediation(
                owner_id, incident, tuple(item.edit_id for item in edits),
            )
        documentation = ()
        if before_verify is not None:
            try:
                documentation = tuple(before_verify(record, edits))
            except Exception:
                return NaturalEngineeringRepairResult(
                    record, edits, (), (), incident, False,
                    "repair_documentation_regeneration_failed",
                )
        verifications = verify(
            owner_id, task.task_id, session_id, principal_id, record,
        )
        passed = all(
            item.status is CandidateVerificationStatus.COMPLETED and item.passed
            for item in verifications
        )
        if passed and incident is not None:
            incident = self._incidents.complete_recovery(
                owner_id, incident,
                tuple(item.verification_id for item in verifications),
            )
        return NaturalEngineeringRepairResult(
            record, edits, verifications, documentation, incident, passed,
            None if passed else "signed_candidate_repair_verification_failed",
        )


def _feedback(records) -> tuple[str, ...]:
    values = []
    for item in records:
        values.append(
            f"verification_id={item.verification_id};"
            f"toolchain={item.toolchain};passed={str(item.passed).lower()}"
        )
        if item.failure_code:
            values.append(f"failure_code={item.failure_code}")
        receipt = getattr(item, "receipt", None)
        if receipt is not None and receipt.diagnostic.strip():
            values.append(f"tool_diagnostic={receipt.diagnostic}")
        if item.evidence is not None:
            values.extend(
                f"unresolved_risk={risk}" for risk in item.evidence.unresolved_risks
            )
    return sanitize_diagnostic_feedback(values)
