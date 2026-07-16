"""README summary through generic, MCP, deterministic-file, and local expert paths."""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.linux import (
    ScopedFileAdapter, ScopedFilePolicy, build_deterministic_registration,
    file_observation,
)
from fam_os.application_acceptance.contracts import (
    IntegrationLevel, ScenarioEvidence,
)
from fam_os.application_acceptance.core_session import (
    AcceptanceCoreSession, plan_factory,
)
from fam_os.application_acceptance.deterministic_provider import DeterministicFileProvider
from fam_os.application_acceptance.generic_linux import observe_unmodified_zenity
from fam_os.application_acceptance.local_expert import LocalReadmeSummarizer
from fam_os.application_acceptance.mcp_reference import observe_reference_server
from fam_os.application_acceptance.metrics import OperationMeter
from fam_os.applications import (
    ApplicationAuthority, PermissionGrant, PermissionScope,
)
from fam_os.core.contracts import (
    PlanStep, PlanStepKind, PlanTransition, StepOutcome, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    ApplicationStepService, ObservationAcquisition, PlanEvidenceKind,
    PlanEvidenceReference,
)


FILE_CAPABILITY = "linux.file.observe"
GENERIC_CAPABILITY = "linux.accessibility.observe"
EXPERT_CAPABILITY = "expert.local.summarize"


class ReadmeSummaryWorkflow:
    def __init__(self, root: Path, mcp_available=True, model_ref="qwen3:1.7b"):
        self.root = root.resolve(strict=True)
        self.mcp_available = mcp_available
        self.model_ref = model_ref
        self.meter = OperationMeter()
        self.core_snapshot = None

    def run(self, request_id, prompt):
        generic, mcp = self._generic_and_mcp(request_id)
        readme = self.root / "README.md"
        entry, provider = self._file_provider(readme)
        mcp_capability = mcp["capability_id"] if mcp else None
        capabilities = tuple(filter(None, (
            GENERIC_CAPABILITY, mcp_capability, FILE_CAPABILITY, EXPERT_CAPABILITY,
        )))
        grants = self._grants(entry, readme, mcp_capability)
        session = AcceptanceCoreSession.start(
            request_id, prompt, self._plan(request_id, capabilities), grants,
            verification_required=False,
        )
        revision = self._context_steps(session, mcp_capability)
        observed = self._observe_file(
            request_id, session, revision, entry, provider, readme,
        )
        response = self._summarize(request_id, observed, mcp)
        self._release(session, observed, request_id)
        result = response.content.strip()
        result += (
            f"\n\nCapabilities used: {', '.join(capabilities)}. "
            f"Expert: {self.model_ref}. Generic nodes: {generic['node_count']}."
        )
        return ScenarioEvidence(
            request_id, True, False, not self.mcp_available, result, capabilities,
            tuple(item.grant_id for item in grants), (self.model_ref,),
            tuple(self.meter.measurements),
        )

    def _generic_and_mcp(self, request_id):
        generic = self.meter.measure(
            f"{request_id}-generic", IntegrationLevel.ACCESSIBILITY,
            GENERIC_CAPABILITY,
            lambda: observe_unmodified_zenity(Path(shutil.which("zenity"))),
        )
        mcp = self._mcp(request_id)
        return generic, mcp

    def _context_steps(self, session, mcp_capability):
        revision = self._advance_observation(
            session, 0, GENERIC_CAPABILITY, "grant-generic", "generic-evidence",
        )
        if mcp_capability:
            revision = self._advance_observation(
                session, revision, mcp_capability, "grant-mcp", "mcp-evidence",
            )
        return revision

    def _observe_file(self, request_id, session, revision, entry, provider, readme):
        observed = self.meter.measure(
            f"{request_id}-file", IntegrationLevel.DETERMINISTIC,
            FILE_CAPABILITY,
            lambda: ApplicationStepService(
                session.lifecycle, provider, session.permissions,
            ).acquire_observation(ObservationAcquisition(
                session.plan_instance_id, revision, session.routed,
                entry.instance_id, "grant-file", {"include_content": True},
                readme.as_uri(),
            )),
            context_selector=lambda value: value.evidence.payload,
        )
        if observed.rejection is not None:
            raise RuntimeError("README observation was rejected")
        return observed

    def _summarize(self, request_id, observed, mcp):
        content = observed.evidence.payload["content"]
        mcp_context = str(mcp["payload"]) if mcp else None
        response = self.meter.measure(
            f"{request_id}-expert", IntegrationLevel.DETERMINISTIC,
            EXPERT_CAPABILITY,
            lambda: LocalReadmeSummarizer(self.model_ref).summarize(content, mcp_context),
            context_selector=lambda value: {
                "readme": content, "mcp_context": mcp_context,
                "summary": value.content,
            },
        )
        return response

    def _release(self, session, observed, request_id):
        candidate_id = f"candidate-{request_id}"
        final = session.lifecycle.advance(
            session.plan_instance_id, observed.snapshot.revision, StepOutcome.SUCCEEDED,
            (PlanEvidenceReference(
                candidate_id, PlanEvidenceKind.RELEASE_CANDIDATE, EXPERT_CAPABILITY,
            ),),
        )
        if final.rejection is not None or not final.snapshot.terminal:
            raise RuntimeError("summary lifecycle did not release")
        self.core_snapshot = final.snapshot

    def _mcp(self, request_id):
        if not self.mcp_available:
            return None
        return self.meter.measure(
            f"{request_id}-mcp", IntegrationLevel.MCP, "mcp.reference.resource",
            lambda: observe_reference_server(self.root),
        )

    def _file_provider(self, readme):
        registration = build_deterministic_registration(
            "acceptance-files", "acceptance-files-instance",
            (file_observation((readme.as_uri(),)),), datetime.now(timezone.utc),
        )
        entry = registration.capabilities[0]
        adapter = ScopedFileAdapter(ScopedFilePolicy((self.root,)))
        return entry, DeterministicFileProvider(entry, adapter)

    def _grants(self, entry, readme, mcp_capability):
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=30)
        values = [PermissionGrant(
            "grant-generic", "local-user", (ApplicationAuthority.OBSERVE,),
            PermissionScope(capability_ids=(GENERIC_CAPABILITY,)), now, expiry,
        )]
        if mcp_capability:
            values.append(PermissionGrant(
                "grant-mcp", "local-user", (ApplicationAuthority.OBSERVE,),
                PermissionScope(capability_ids=(mcp_capability,)), now, expiry,
            ))
        values.append(PermissionGrant(
            "grant-file", "local-user", (ApplicationAuthority.OBSERVE,),
            PermissionScope(
                application_ids=(entry.application_id,),
                instance_ids=(entry.instance_id,), capability_ids=(FILE_CAPABILITY,),
                resource_uris=(readme.as_uri(),),
            ), now, expiry,
        ))
        return tuple(values)

    @staticmethod
    def _advance_observation(session, revision, capability, grant, evidence):
        advanced = session.lifecycle.advance(
            session.plan_instance_id, revision, StepOutcome.SUCCEEDED,
            (PlanEvidenceReference(
                evidence, PlanEvidenceKind.OBSERVATION, capability, grant,
            ),),
        )
        if advanced.rejection is not None:
            raise RuntimeError("acceptance observation transition failed")
        return advanced.snapshot.revision

    @staticmethod
    def _plan(request_id, capabilities):
        steps = []
        for index, capability in enumerate(capabilities[:-1]):
            steps.append(PlanStep(
                f"observe-{index}", PlanStepKind.OBSERVE,
                f"Acquire {capability}", (capability,),
            ))
        steps.append(PlanStep(
            "summarize", PlanStepKind.INFERENCE, "Summarize README",
            (EXPERT_CAPABILITY,),
        ))
        steps.extend((
            PlanStep("release", PlanStepKind.FINALIZE, "Release summary",
                     terminal_disposition=TerminalDisposition.RELEASE),
            PlanStep("fail", PlanStepKind.FINALIZE, "Fail safely",
                     terminal_disposition=TerminalDisposition.FAIL),
        ))
        transitions = []
        active = steps[:-2]
        for index, step in enumerate(active):
            target = active[index + 1].step_id if index + 1 < len(active) else "release"
            transitions.append(PlanTransition(step.step_id, StepOutcome.SUCCEEDED, target))
            transitions.append(PlanTransition(step.step_id, StepOutcome.FAILED, "fail"))
        return plan_factory(
            f"plan-{request_id}", request_id, capabilities,
            tuple(steps), tuple(transitions), verification_required=False,
        )
