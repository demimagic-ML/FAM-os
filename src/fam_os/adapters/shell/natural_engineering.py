"""Project natural engineering into existing Shell task and approval contracts."""

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fam_os.core.contracts import ResultAssurance, ResultKind, ResultStatus
from fam_os.shell.contracts import (
    ShellApprovalRequest, ShellAskCommand, ShellDecision,
    ShellContextKind, ShellDecisionCommand, ShellPlanStep, ShellResult,
    ShellRunState,
    ShellSessionSnapshot, ShellSnapshotQuery, ShellStepState,
)


_PREFIX = "natural-engineering:"


class NaturalEngineeringShellAdapter:
    def __init__(self, api) -> None:
        self._api = api

    def handles_ask(self, command: ShellAskCommand) -> bool:
        # Application contexts carry their own capability router and may also
        # include a workspace URI as a parameter.  They must stay on that
        # existing route; otherwise the broad natural-engineering handler
        # steals directory and legacy workspace actions before their explicit
        # application capabilities can be evaluated.
        return (
            _workspace(command) is not None
            and command.remote_authority is None
            and all(
                context.kind is not ShellContextKind.APPLICATION
                for context in command.contexts
            )
        )

    def propose(self, command: ShellAskCommand) -> ShellSessionSnapshot:
        workspace = _workspace(command)
        if workspace is None:
            raise ValueError("natural engineering requires one local workspace")
        proposal = self._api.propose(
            self._api.owner_id, command.prompt, str(workspace),
            transport_session_id=command.memory_session_id,
        )
        return self._proposal_snapshot(command.request_id, proposal)

    def handles_session(self, session_id: str) -> bool:
        return session_id.startswith(_PREFIX)

    def decide(self, command: ShellDecisionCommand) -> ShellSessionSnapshot:
        proposal_id, request_id = _session(command.session_id)
        current = self._api.progress(self._api.owner_id, proposal_id)
        expected = _approval_id(current)
        if command.approval_id != expected:
            raise PermissionError("Shell natural engineering approval changed")
        if command.decision is ShellDecision.DENY:
            if (
                current.get("engineering_task") is not None
                and current["engineering_task"].get("outcome")
                == "publication_approval_required"
            ):
                self._api.approve_publication(
                    self._api.owner_id, proposal_id, expected,
                    command.session_id, confirmed=False,
                )
                return _kept(
                    command.session_id, request_id,
                    command.expected_revision + 1,
                    current["engineering_task"],
                )
            if (
                current.get("engineering_task") is not None
                and current["engineering_task"].get("outcome")
                in {
                    "local_commit_completed", "publication_approval_required",
                    "postapply_verification_failed", "independent_review_blocked",
                }
            ):
                return _kept(
                    command.session_id, request_id,
                    command.expected_revision + 1,
                    current["engineering_task"],
                )
            self._api.decline(self._api.owner_id, proposal_id)
            return _withheld(command.session_id, request_id, command.expected_revision + 1)
        if current["engineering_task"] is None:
            resource = current["proposal"].get("integration_resource_grant")
            if resource is not None and resource["status"] != "approved":
                response = self._api.approve_integration_resources(
                    self._api.owner_id, proposal_id, command.session_id,
                    confirmed=True,
                )
            else:
                response = self._api.activate(
                    self._api.owner_id, proposal_id, command.session_id,
                    confirmed=True,
                )
        elif current["engineering_task"].get("outcome") == "changeset_approval_required":
            response = self._api.approve_changeset(
                self._api.owner_id, proposal_id, expected,
                command.session_id, confirmed=True,
            )
        elif current["engineering_task"].get("outcome") == "independent_review_blocked":
            waiver = current["engineering_task"]["review_waiver_checkpoint"]
            response = self._api.waive_review(
                self._api.owner_id, proposal_id, waiver["checkpoint_id"],
                waiver["finding_id"], waiver["consequences_sha256"],
                command.session_id, confirmed=True,
            )
        elif current["engineering_task"].get("outcome") == "publication_approval_required":
            response = self._api.approve_publication(
                self._api.owner_id, proposal_id, expected,
                command.session_id, confirmed=True,
            )
        else:
            response = self._api.rollback(
                self._api.owner_id, proposal_id, expected,
                command.session_id, confirmed=True,
            )
        return self._outcome_snapshot(
            command.session_id, request_id, command.expected_revision + 1,
            response,
        )

    def snapshot(self, command: ShellSnapshotQuery) -> ShellSessionSnapshot:
        proposal_id, request_id = _session(command.session_id)
        progress = self._api.progress(self._api.owner_id, proposal_id)
        return self._outcome_snapshot(command.session_id, request_id, 1, progress)

    def _proposal_snapshot(self, request_id, proposal, revision=0):
        session_id = f"{_PREFIX}{proposal['proposal_id']}:{request_id}"
        grant = proposal["grant"]["payload"]
        authorities = ", ".join(grant["authorities"])
        separate = proposal["separately_confirmed_authorities"]
        resource = proposal.get("integration_resource_grant")
        resource_grant = None if resource is None else resource["document"]["payload"]
        resource_authorities = (
            () if resource_grant is None else tuple(
                value for value in resource_grant["authorities"]
                if value != "execute"
            )
        )
        blocked = tuple(
            value for value in separate
            if value != "publish" and value not in resource_authorities
        )
        if blocked:
            reason = "Separate owner ceremonies required: " + ", ".join(blocked)
            return _failed(session_id, request_id, revision, reason)
        if resource is not None and resource["status"] != "approved":
            approval = ShellApprovalRequest(
                resource_grant["grant_id"], proposal["proposal_id"],
                "engineering.integration.resources.activate",
                _integration_resource_summary(resource),
                datetime.fromisoformat(resource_grant["expires_at"]), True,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.WAITING_APPROVAL,
                _steps("resources"), "resources",
                "No process, network, secret, or repository effect has occurred.",
                approval,
            )
        approval = ShellApprovalRequest(
            f"grant:{proposal['proposal_id']}", proposal["proposal_id"],
            "engineering.grant.activate",
            f"Authorize {authorities} in {grant['scope']['workspace_roots'][0]}",
            datetime.fromisoformat(grant["expires_at"]), True,
        )
        return ShellSessionSnapshot(
            session_id, request_id, revision, ShellRunState.WAITING_APPROVAL,
            _steps("grant"), "grant", "No repository effect has occurred.",
            approval,
        )

    def _outcome_snapshot(self, session_id, request_id, revision, response):
        task = response.get("engineering_task")
        if task is None:
            proposal = response["proposal"]
            if proposal.get("status") == "failed":
                return _failed(
                    session_id, request_id, revision,
                    proposal.get("failure_code") or "engineering proposal failed",
                )
            return self._proposal_snapshot(request_id, proposal, revision)
        outcome = task.get("outcome")
        if outcome == "independent_review_blocked":
            waiver = task["review_waiver_checkpoint"]
            summary = _review_waiver_summary(waiver)
            approval = ShellApprovalRequest(
                waiver["finding_id"], waiver["checkpoint_id"],
                "engineering.review.waive", summary,
                datetime.fromisoformat(
                    response["proposal"]["grant"]["payload"]["expires_at"]
                ),
                True,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision,
                ShellRunState.WAITING_APPROVAL,
                _steps("review"), "review", summary, approval,
            )
        if outcome == "changeset_approval_required":
            changeset = task["changeset"]["payload"]
            summary = _changeset_summary(changeset)
            approval = ShellApprovalRequest(
                changeset["changeset_id"], changeset["changeset_id"],
                "engineering.changeset.apply", summary,
                datetime.fromisoformat(response["proposal"]["grant"]["payload"]["expires_at"]),
                True,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.WAITING_APPROVAL,
                _steps("changeset"), "changeset", summary, approval,
            )
        if outcome == "publication_approval_required":
            publication = task["publication_proposal"]["document"]["payload"]
            summary = _publication_summary(
                publication,
                task["publication_proposal"]["approval_sha256"],
            )
            approval = ShellApprovalRequest(
                publication["proposal_id"], publication["proposal_id"],
                "engineering.git.publish", summary,
                datetime.fromisoformat(publication["expires_at"]), True,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.WAITING_APPROVAL,
                _steps("publication"), "publication", summary, approval,
            )
        if (
            outcome == "postapply_verification_failed"
            and task.get("rollback_checkpoint") is not None
        ):
            rollback = task["rollback_checkpoint"]
            summary = _rollback_summary(rollback)
            approval = ShellApprovalRequest(
                rollback["rollback_id"], rollback["rollback_id"],
                "engineering.changeset.rollback", summary,
                datetime.fromisoformat(
                    response["proposal"]["grant"]["payload"]["expires_at"]
                ),
                True,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision,
                ShellRunState.WAITING_APPROVAL,
                _steps("recovery_rollback"), "rollback",
                "Post-apply verification failed; the exact uncommitted rollback is available.",
                approval,
            )
        if outcome == "local_commit_completed":
            evidence = tuple(dict.fromkeys(
                (*task.get("test_receipt_ids", ()), *task.get("git_receipt_ids", ())),
            ))
            rollback = task.get("rollback_checkpoint")
            if rollback is not None:
                approval = ShellApprovalRequest(
                    rollback["rollback_id"], rollback["rollback_id"],
                    "engineering.changeset.rollback",
                    _rollback_summary(rollback),
                    datetime.fromisoformat(
                        response["proposal"]["grant"]["payload"]["expires_at"]
                    ),
                    True,
                )
                return ShellSessionSnapshot(
                    session_id, request_id, revision,
                    ShellRunState.WAITING_APPROVAL,
                    _steps("rollback"), "rollback",
                    "Verified local commit completed; optional exact rollback is available.",
                    approval,
                )
            result = ShellResult(
                request_id, ResultStatus.VERIFIED,
                "Approved changes were applied, reverified, and committed locally.",
                verified=True, evidence_ids=evidence,
                assurance=ResultAssurance.VERIFIED,
                result_kind=ResultKind.ACTION_RECEIPT,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.TERMINAL,
                _steps("complete"), None, "Engineering lifecycle completed.",
                result=result,
            )
        if outcome == "rollback_completed":
            evidence = tuple(dict.fromkeys((
                *task.get("rollback_receipt_ids", ()),
                *task.get("git_receipt_ids", ()),
            )))
            committed = task.get("git_rollback_delivery") is not None
            result = ShellResult(
                request_id, ResultStatus.VERIFIED,
                (
                    "Approved rollback restored the exact FAM-owned paths and "
                    + (
                        "created a separate local commit."
                        if committed else "left Git history unchanged."
                    )
                ),
                verified=True, evidence_ids=evidence,
                assurance=ResultAssurance.VERIFIED,
                result_kind=ResultKind.ACTION_RECEIPT,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.TERMINAL,
                _steps("rolled_back"), None, "Engineering rollback completed.",
                result=result,
            )
        if outcome == "publication_completed":
            receipt = task.get("publication_receipt", {}).get("payload", {})
            reference = receipt.get("change_request_url")
            result = ShellResult(
                request_id, ResultStatus.VERIFIED,
                "The exact verified commit was published through the separately approved credential-opaque broker."
                + (f" Draft change request: {reference}" if reference else ""),
                verified=True,
                evidence_ids=tuple(dict.fromkeys((
                    *task.get("test_receipt_ids", ()),
                    *task.get("git_receipt_ids", ()),
                    receipt.get("receipt_id", "publication-receipt"),
                ))),
                assurance=ResultAssurance.VERIFIED,
                result_kind=ResultKind.ACTION_RECEIPT,
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.TERMINAL,
                _steps("published"), None, "Engineering publication completed.",
                result=result,
            )
        if outcome == "analysis_ready":
            result = ShellResult(
                request_id, ResultStatus.COMPLETED,
                "Repository analysis completed without modification authority.",
            )
            return ShellSessionSnapshot(
                session_id, request_id, revision, ShellRunState.TERMINAL,
                _steps("analysis"), result=result,
            )
        return _failed(
            session_id, request_id, revision,
            _failure_reason(task),
        )


def _workspace(command):
    values = []
    for context in command.contexts:
        value = context.resource_ref
        if value.startswith("file://"):
            parsed = urlsplit(value)
            if parsed.netloc not in {"", "localhost"}:
                continue
            value = unquote(parsed.path)
        path = Path(value)
        if path.is_absolute() and path.is_dir() and not path.is_symlink():
            values.append(path.resolve(strict=True))
    unique = tuple(dict.fromkeys(values))
    return unique[0] if len(unique) == 1 else None


def _session(session_id):
    if not session_id.startswith(_PREFIX):
        raise ValueError("Shell natural engineering session is invalid")
    proposal_id, separator, request_id = session_id[len(_PREFIX):].rpartition(":")
    if not separator or not proposal_id or not request_id:
        raise ValueError("Shell natural engineering session is invalid")
    return proposal_id, request_id


def _approval_id(response):
    task = response.get("engineering_task")
    if task is None:
        resource = response["proposal"].get("integration_resource_grant")
        if resource is not None and resource["status"] != "approved":
            return resource["document"]["payload"]["grant_id"]
        return f"grant:{response['proposal']['proposal_id']}"
    if task.get("outcome") == "changeset_approval_required":
        return task["changeset"]["payload"]["changeset_id"]
    if task.get("outcome") == "independent_review_blocked":
        return task["review_waiver_checkpoint"]["finding_id"]
    if task.get("outcome") == "local_commit_completed":
        return task["rollback_checkpoint"]["rollback_id"]
    if task.get("outcome") == "postapply_verification_failed":
        return task["rollback_checkpoint"]["rollback_id"]
    if task.get("outcome") == "publication_approval_required":
        return task["publication_proposal"]["document"]["payload"]["proposal_id"]
    raise PermissionError("Shell natural engineering is not waiting for approval")


def _steps(stage):
    if stage == "resources":
        return (
            ShellPlanStep(
                "resources", "resources", "Approve exact integration resources",
                ShellStepState.ACTIVE,
            ),
            ShellPlanStep(
                "grant", "grant", "Authorize bounded task",
                ShellStepState.PENDING,
            ),
            ShellPlanStep(
                "changeset", "changeset", "Verify and approve changeset",
                ShellStepState.PENDING,
            ),
        )
    if stage == "review":
        return (
            ShellPlanStep(
                "grant", "grant", "Authorize bounded task",
                ShellStepState.SUCCEEDED,
            ),
            ShellPlanStep(
                "candidate", "candidate", "Generate and verify candidate",
                ShellStepState.SUCCEEDED,
            ),
            ShellPlanStep(
                "review", "review", "Resolve or explicitly waive review finding",
                ShellStepState.ACTIVE,
            ),
            ShellPlanStep(
                "changeset", "changeset", "Approve exact changeset",
                ShellStepState.PENDING,
            ),
        )
    if stage in {"publication", "published"}:
        publication_state = (
            ShellStepState.ACTIVE
            if stage == "publication" else ShellStepState.SUCCEEDED
        )
        values = (
            ("grant", "Authorize bounded task", ShellStepState.SUCCEEDED),
            ("changeset", "Verify and approve changeset", ShellStepState.SUCCEEDED),
            ("complete", "Apply, reverify, and commit", ShellStepState.SUCCEEDED),
            ("publication", "Separately approve exact push and draft PR", publication_state),
        )
        return tuple(
            ShellPlanStep(identity, identity, description, state)
            for identity, description, state in values
        )
    if stage in {"rollback", "rolled_back", "rollback_kept"}:
        rollback_state = {
            "rollback": ShellStepState.ACTIVE,
            "rolled_back": ShellStepState.SUCCEEDED,
            "rollback_kept": ShellStepState.DENIED,
        }[stage]
        values = (
            ("grant", "Authorize bounded task", ShellStepState.SUCCEEDED),
            ("changeset", "Verify and approve changeset", ShellStepState.SUCCEEDED),
            ("complete", "Apply, reverify, and commit", ShellStepState.SUCCEEDED),
            ("rollback", "Restore exact FAM-owned paths", rollback_state),
        )
        return tuple(
            ShellPlanStep(identity, identity, description, state)
            for identity, description, state in values
        )
    if stage == "recovery_rollback":
        return (
            ShellPlanStep(
                "grant", "grant", "Authorize bounded task",
                ShellStepState.SUCCEEDED,
            ),
            ShellPlanStep(
                "changeset", "changeset", "Verify and approve changeset",
                ShellStepState.SUCCEEDED,
            ),
            ShellPlanStep(
                "complete", "complete", "Post-apply verification",
                ShellStepState.FAILED,
            ),
            ShellPlanStep(
                "rollback", "rollback", "Restore exact FAM-owned paths",
                ShellStepState.ACTIVE,
            ),
        )
    states = {
        "grant": (ShellStepState.ACTIVE, ShellStepState.PENDING, ShellStepState.PENDING),
        "changeset": (ShellStepState.SUCCEEDED, ShellStepState.ACTIVE, ShellStepState.PENDING),
        "complete": (ShellStepState.SUCCEEDED,) * 3,
        "analysis": (ShellStepState.SUCCEEDED, ShellStepState.SUCCEEDED, ShellStepState.CANCELLED),
    }[stage]
    return tuple(
        ShellPlanStep(identity, identity, description, state)
        for identity, description, state in zip(
            ("grant", "changeset", "complete"),
            ("Authorize bounded task", "Verify and approve changeset", "Apply, reverify, and commit"),
            states, strict=True,
        )
    )


def _changeset_summary(changeset):
    rows = []
    for item in changeset["preview"]["items"]:
        preview = " ".join(item["preview"].split())[:500]
        rows.append(f"{item['operation_kind']} {item['path']}: {preview}")
    return "Apply exact verified changeset " + changeset["changeset_id"] + " | " + " | ".join(rows)


def _rollback_summary(rollback):
    paths = ", ".join(rollback["paths"])
    consequences = "; ".join(rollback.get("consequences", ()))
    return (
        f"Restore unchanged FAM-owned paths: {paths}"
        + (f" | {consequences}" if consequences else "")
    )


def _review_waiver_summary(waiver):
    location = f" at {waiver['path']}" if waiver.get("path") else ""
    return (
        f"Explicitly waive {waiver['severity']} {waiver['discipline']} finding "
        f"{waiver['finding_id']}{location}: {waiver['title']}; this does not "
        f"claim resolution and yields {waiver['truthful_assurance_after_waiver']}; "
        f"exact consequences digest {waiver['consequences_sha256']}"
    )


def _publication_summary(proposal, digest):
    consequences = "; ".join(proposal["consequence_preview"])
    return (
        f"Publish exact verified commits {', '.join(proposal['commit_object_ids'])} "
        f"from {proposal['source_ref']} to {proposal['remote_name']} "
        f"{proposal['target_ref']}; expected old object "
        f"{proposal['expected_old_object_id'] or 'absent'}; complete diff "
        f"{proposal['complete_diff_sha256']}; verification "
        f"{', '.join(proposal['verification_evidence_ids'])}; title "
        f"{proposal['title']}; body {proposal['body']}; opaque credential "
        f"{proposal['credential_ref']}; consequences {consequences}; "
        f"approval digest {digest}"
    )


def _integration_resource_summary(resource):
    grant = resource["document"]["payload"]
    scope = grant["scope"]
    network = ", ".join(scope["network_hosts"]) or "none"
    secrets = ", ".join(scope["secret_refs"]) or "none"
    authorities = ", ".join(
        value for value in grant["authorities"] if value != "execute"
    )
    return (
        f"Authorize exact {authorities} integration scope for task "
        f"{scope['scope_id']}; destinations {network}; opaque secret refs "
        f"{secrets}; maximum network bytes "
        f"{grant['resource_impact']['max_network_bytes']}; maximum ephemeral "
        f"integration storage bytes "
        f"{grant['resource_impact']['max_changed_bytes']}; PostgreSQL secret "
        f"consumer integration:postgresql with tool key POSTGRES_PASSWORD; "
        f"approval digest "
        f"{resource['approval_sha256']}"
    )


def _failure_reason(task):
    reason = task.get("failure_code") or task.get("outcome") or "engineering lifecycle unavailable"
    incident = task.get("incident", {}).get("payload", {})
    if not incident:
        return reason
    evidence = ", ".join(incident.get("symptom_evidence_ids", ())) or "none"
    return (
        f"{reason}; incident {incident.get('incident_id', 'unknown')} is "
        f"{incident.get('stage', 'unknown')}; symptom evidence: {evidence}"
    )


def _failed(session_id, request_id, revision, reason):
    result = ShellResult(request_id, ResultStatus.FAILED, None, reason=reason)
    return ShellSessionSnapshot(
        session_id, request_id, revision, ShellRunState.TERMINAL,
        (), None, "Engineering lifecycle stopped safely.", result=result,
    )


def _withheld(session_id, request_id, revision):
    result = ShellResult(
        request_id, ResultStatus.WITHHELD, None, reason="Owner denied the proposal.",
        result_kind=ResultKind.ACTION_PROPOSAL,
    )
    return ShellSessionSnapshot(
        session_id, request_id, revision, ShellRunState.TERMINAL,
        (), None, "No effect was executed.", result=result,
    )


def _kept(session_id, request_id, revision, task):
    evidence = tuple(dict.fromkeys((
        *task.get("test_receipt_ids", ()), *task.get("git_receipt_ids", ()),
    )))
    result = ShellResult(
        request_id, ResultStatus.VERIFIED,
        "Approved changes were applied, reverified, and kept as a local commit.",
        verified=True, evidence_ids=evidence,
        assurance=ResultAssurance.VERIFIED,
        result_kind=ResultKind.ACTION_RECEIPT,
    )
    return ShellSessionSnapshot(
        session_id, request_id, revision, ShellRunState.TERMINAL,
        _steps(
            "rollback_kept"
            if task.get("outcome") == "local_commit_completed"
            and task.get("rollback_checkpoint") is not None
            else "complete"
        ),
        None, "Engineering lifecycle completed.",
        result=result,
    )
