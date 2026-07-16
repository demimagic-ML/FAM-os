"""FAM Shell gateway backed by real Phase 5 acceptance workflows."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.application_acceptance.edit_workflow import VsCodeEditWorkflow
from fam_os.application_acceptance.summary_workflow import ReadmeSummaryWorkflow
from fam_os.application_acceptance.test_workflow import BoundedTestWorkflow
from fam_os.core.contracts import ResultStatus, TaskResult
from fam_os.core.ingress.shell_views import accepted_shell_snapshot, project_shell_snapshot
from fam_os.shell import ShellApprovalRequest, ShellDecision


@dataclass(slots=True)
class _Session:
    request_id: str
    kind: str
    workflow: object
    revision: int = 0
    outcome: object | None = None


class AcceptanceShellGateway:
    def __init__(self, root: Path, workspace: Path, edit_target: Path, mcp_available=True):
        self.root = root
        self.workspace = workspace
        self.edit_target = edit_target
        self.mcp_available = mcp_available
        self._sessions = {}
        self.completed = []

    def ask(self, command):
        kind, workflow = self._workflow(command.prompt)
        session_id = f"acceptance-{uuid4()}"
        self._sessions[session_id] = _Session(command.request_id, kind, workflow)
        return accepted_shell_snapshot(
            session_id, command.request_id,
            f"Accepted {kind} through real Application Fabric adapters.",
        )

    def snapshot(self, session_id):
        session = self._require(session_id)
        if session.revision != 0:
            raise RuntimeError("acceptance session cannot be refreshed again")
        if session.kind == "edit":
            core = session.workflow.prepare(session.request_id, "Edit acceptance file")
            session.revision = 1
            proposal = session.workflow.proposal
            approval = ShellApprovalRequest(
                f"approval-{session.request_id}", proposal.proposal_id,
                "vscode.workspace_edit.apply",
                "Preview: replace 'Before' with 'After' on line 1 of the temporary file.",
                datetime.now(timezone.utc) + timedelta(minutes=5), True,
            )
            return project_shell_snapshot(
                session_id, core, 1, approval=approval,
                message="Native editor change is prepared and requires approval.",
            )
        outcome = session.workflow.run(session.request_id, session.kind)
        session.outcome = outcome
        session.revision = 1
        self.completed.append(outcome)
        return project_shell_snapshot(
            session_id, session.workflow.core_snapshot, 1,
            result=_task_result(outcome, session.workflow.core_snapshot.plan.plan_id),
            message="Acceptance workflow completed.",
        )

    def decide(self, command):
        session = self._require(command.session_id)
        if session.kind != "edit" or command.expected_revision != session.revision:
            raise RuntimeError("shell decision does not match the edit session")
        approved = command.decision is ShellDecision.APPROVE
        try:
            outcome = session.workflow.execute(session.request_id, approved)
            session.outcome = outcome
            session.revision += 1
            self.completed.append(outcome)
            snapshot = session.workflow.session.lifecycle.repository.get(
                session.workflow.session.plan_instance_id
            )
            return project_shell_snapshot(
                command.session_id, snapshot, session.revision,
                result=_task_result(outcome, snapshot.plan.plan_id),
                message="Approved native editor action completed.",
            )
        finally:
            session.workflow.close()

    def cancel(self, command):
        session = self._require(command.session_id)
        if session.kind == "edit":
            session.workflow.close()
        raise RuntimeError("acceptance cancellation is not part of the measured scenarios")

    def close(self):
        for session in self._sessions.values():
            if session.kind == "edit":
                session.workflow.close()

    def _workflow(self, prompt):
        normalized = prompt.strip().casefold()
        if normalized == "summarize the current project readme":
            return "summary", ReadmeSummaryWorkflow(
                self.root, self.mcp_available,
            )
        if normalized == "run the application action contract test":
            return "test", BoundedTestWorkflow(self.root)
        if normalized == "edit the temporary acceptance file":
            return "edit", VsCodeEditWorkflow(
                self.root, self.workspace, self.edit_target,
            )
        raise ValueError("acceptance prompt is not an approved bounded scenario")

    def _require(self, session_id):
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("acceptance shell session does not exist")
        return session


def _task_result(outcome, plan_id):
    if not outcome.succeeded:
        raise RuntimeError("acceptance workflow did not produce releasable content")
    status = ResultStatus.VERIFIED if outcome.verified else ResultStatus.COMPLETED
    evidence = tuple(
        dict.fromkeys((
            *outcome.audit_event_ids,
            *(item.operation_id for item in outcome.measurements if item.succeeded),
        ))
    )
    return TaskResult(
        outcome.scenario_id, status, outcome.result, outcome.verified,
        plan_id=plan_id, evidence_ids=evidence,
    )
