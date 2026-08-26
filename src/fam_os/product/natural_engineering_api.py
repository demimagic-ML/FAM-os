"""Authenticated product facade from natural language to engineering preparation."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.core.agent import AgentAuthorityProfile
from fam_os.core.engineering import (
    BreakGlassChallenge,
    BreakGlassDecision,
    BreakGlassDisposition,
    CandidateVerificationStatus,
    CheckpointDecision,
    CheckpointDisposition,
    EngineeringAuthority,
    EngineeringOperation,
    NaturalEngineeringConversation,
    NaturalLanguageEngineeringPlanner,
    OwnerGrantApproval,
    architecture_plan_view,
    candidate_preview_digest,
    consequences_digest,
)
from fam_os.core.engineering.grant_policy import engineering_grant_digest
from fam_os.schemas import encode_document
from fam_os.product.natural_engineering_publication import (
    NaturalEngineeringPublicationCoordinator,
)
from fam_os.product.natural_engineering_incidents import (
    NaturalEngineeringIncidentCoordinator,
)
from fam_os.product.natural_engineering_integration_authority import (
    NaturalEngineeringIntegrationAuthorityCoordinator,
)
from fam_os.product.natural_engineering_review_governance import (
    NaturalEngineeringReviewGovernance,
)
from fam_os.product.owner_engineering_authentication import (
    break_glass_authentication_digest,
)


class ProductNaturalEngineeringApi:
    def __init__(
        self, owner_id, proposals, authentication, authorizer, loop, observer,
        *, executor=None, clock=None, identifier=None,
        publication_remote_name=None, publication_credential_ref=None,
        grant_reader=None, conversation: NaturalEngineeringConversation | None = None,
    ) -> None:
        self.owner_id = owner_id
        self._proposals = proposals
        self._authentication = authentication
        self._authorizer = authorizer
        self._loop = loop
        self._observer = observer
        self._executor = executor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: uuid4().hex)
        self._planner = NaturalLanguageEngineeringPlanner()
        self._conversation = conversation
        self._publication = NaturalEngineeringPublicationCoordinator(
            loop, remote_name=publication_remote_name,
            credential_ref=publication_credential_ref,
            activate_grant=self._activate_grant_document,
            attach_rollback=self._attach_rollback_checkpoint,
        )
        self._incidents = NaturalEngineeringIncidentCoordinator(loop)
        self._review_governance = NaturalEngineeringReviewGovernance(
            loop, authentication, self._clock,
        )
        self._integration_authority = (
            NaturalEngineeringIntegrationAuthorityCoordinator(
                grant_reader, self._activate_grant_document,
            )
        )

    def propose(
        self, owner_id: str, prompt: str, workspace_root: str,
        *, transport_session_id: str | None = None,
        authority_profile: AgentAuthorityProfile = AgentAuthorityProfile.WORKSPACE,
    ) -> dict:
        self._require_owner(owner_id)
        workspace = Path(workspace_root)
        canonical = workspace.resolve(strict=True)
        if canonical != workspace or not canonical.is_dir() or canonical.is_symlink():
            raise PermissionError("engineering workspace must be an exact real directory")
        token = self._identifier()
        task_id, grant_id = f"engineering-{token}", f"grant-{token}"
        evidence = self._observer.observe(task_id, str(canonical))
        canonical = Path(getattr(evidence, "workspace_root", str(canonical)))
        task_intent = (
            prompt if self._conversation is None else self._conversation.resolve(
                owner_id, transport_session_id, str(canonical), prompt,
            )
        )
        proposal = self._planner.propose(
            prompt=prompt, workspace_root=str(canonical), owner_id=owner_id,
            principal_id=owner_id, task_id=task_id, grant_id=grant_id,
            toolchains=_toolchains(evidence), now=self._clock(),
            task_intent=task_intent,
            authority_profile=authority_profile,
            git_available=(
                getattr(getattr(evidence, "git_state", None), "head_revision", None)
                != "unversioned"
            ),
        )
        self._proposals.put(proposal)
        return self._view(proposal)

    def inspect(self, owner_id: str, proposal_id: str) -> dict:
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        if proposal.grant.owner_id != owner_id:
            raise PermissionError("natural engineering proposal owner is invalid")
        return self._view(proposal)

    def thread(
        self, owner_id: str, transport_session_id: str, workspace_root: str,
    ) -> dict[str, object]:
        self._require_owner(owner_id)
        if self._executor is None:
            raise LookupError("iterative engineering agent is unavailable")
        workspace = Path(workspace_root)
        canonical = workspace.resolve(strict=True)
        if canonical != workspace or not canonical.is_dir() or canonical.is_symlink():
            raise PermissionError("engineering workspace must be an exact real directory")
        return self._executor.thread(
            owner_id, transport_session_id, str(canonical),
        )

    def candidate_workspace(
        self, owner_id: str, proposal_id: str,
    ) -> dict[str, object]:
        """Return a bounded, owner-visible view of the real isolated candidate."""
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        task_id = proposal.definition.task.task_id
        preparation = self._loop.preparation(owner_id, task_id)
        observer = getattr(self._loop, "observe_candidate", None)
        if observer is None:
            observer = self._loop.current_candidate
        candidate = observer(owner_id, task_id)
        baseline = {item.path: item for item in preparation.candidate.entries}
        current = {item.path: item for item in candidate.entries}
        entries = []
        counts = {"created": 0, "modified": 0, "deleted": 0, "unchanged": 0}
        for path in sorted(set(baseline) | set(current))[:2_000]:
            before, after = baseline.get(path), current.get(path)
            if before is None:
                status = "created"
            elif after is None:
                status = "deleted"
            elif (
                before.kind != after.kind
                or before.content_sha256 != after.content_sha256
                or before.executable != after.executable
            ):
                status = "modified"
            else:
                status = "unchanged"
            counts[status] += 1
            item = after or before
            entries.append({
                "path": path,
                "kind": item.kind.value,
                "status": status,
                "size_bytes": item.size_bytes,
            })
        return {
            "candidate_id": candidate.candidate_id,
            "task_id": task_id,
            "owner_workspace": candidate.owner_workspace,
            "candidate_workspace": candidate.candidate_workspace,
            "isolated": candidate.owner_workspace != candidate.candidate_workspace,
            "entries": entries,
            "counts": counts,
            "truncated": len(set(baseline) | set(current)) > len(entries),
        }

    def control_thread(
        self, owner_id: str, transport_session_id: str, workspace_root: str,
        kind: str, content: str,
    ) -> dict[str, object]:
        self._require_owner(owner_id)
        if self._executor is None:
            raise LookupError("iterative engineering agent is unavailable")
        workspace = Path(workspace_root)
        canonical = workspace.resolve(strict=True)
        if canonical != workspace or not canonical.is_dir() or canonical.is_symlink():
            raise PermissionError("engineering workspace must be an exact real directory")
        if kind not in {"steer", "cancel"}:
            raise ValueError("agent control kind is invalid")
        return self._executor.control_thread(
            owner_id, transport_session_id, str(canonical), kind, content,
        )

    def restore_goal_grant(
        self, owner_id: str, proposal_id: str, transport_session_id: str,
    ) -> None:
        """Restore the exact persisted grant for an already approved durable goal."""
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        self._activate_grant(owner_id, proposal, transport_session_id)

    def progress(self, owner_id: str, proposal_id: str) -> dict:
        """Reconstruct the current owner-visible proposal and lifecycle checkpoint."""
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        response = {"proposal": self._view(proposal), "engineering_task": None}
        try:
            task = self._loop.inspect(owner_id, proposal.definition.task.task_id)
        except KeyError:
            return response
        database_results = self._loop.database_results(
            owner_id, proposal.definition.task.task_id,
        )
        if database_results:
            task["database_engineering"] = _database_result_view(
                database_results[0]
            )
        database_postapply = self._loop.database_postapply_receipts(
            owner_id, proposal.definition.task.task_id,
        )
        if database_postapply:
            task["postapply_database_receipts"] = [
                encode_document(item) for item in database_postapply
            ]
        integration_reader = getattr(
            self._executor, "integration_environments", None,
        )
        if integration_reader is not None:
            environments = integration_reader(
                owner_id, proposal.definition.task.task_id,
            )
            if environments:
                task["integration_environments"] = [
                    _integration_environment_view(item) for item in environments
                ]
        if task.get("stage") == "changeset_approval_required":
            changeset_id = task.get("diff_checkpoint_id")
            changeset = self._exact_changeset(
                owner_id, proposal.definition.task.task_id, changeset_id,
            )
            task["outcome"] = "changeset_approval_required"
            task["changeset"] = encode_document(changeset)
        elif task.get("stage") == "committed":
            task["outcome"] = "local_commit_completed"
            self._attach_rollback_checkpoint(
                task, owner_id, proposal.definition.task.task_id,
            )
            self._publication.attach(
                task, proposal, create=False,
            )
        elif task.get("stage") == "completed":
            publication = self._loop.publication_for_task(
                owner_id, proposal.definition.task.task_id,
            )
            if publication is not None:
                task["outcome"] = "publication_completed"
                task["publication_proposal"] = self._publication.view(
                    publication,
                )
                receipt = self._loop.publication_receipt(
                    owner_id, publication.proposal_id,
                )
                if receipt is not None:
                    task["publication_receipt"] = encode_document(receipt)
        elif task.get("stage") == "rolled_back":
            task["outcome"] = "rollback_completed"
        incident_reader = getattr(self._loop, "incidents_for_task", None)
        incidents = () if incident_reader is None else incident_reader(
            owner_id, proposal.definition.task.task_id,
        )
        if incidents:
            task["incidents"] = [encode_document(item) for item in incidents]
            task["incident"] = encode_document(incidents[-1])
            evidence_reader = getattr(
                self._loop, "incident_evidence_for_task", None,
            )
            if evidence_reader is not None:
                task["incident_evidence"] = [
                    encode_document(item) for item in evidence_reader(
                        owner_id, proposal.definition.task.task_id,
                    )
                ]
            if task.get("stage") == "applied":
                latest = incidents[-1]
                if latest.stage.value in {
                    "diagnosed", "remediation_proposed",
                }:
                    task["outcome"] = "postapply_verification_failed"
                    evidence = (
                        () if evidence_reader is None else evidence_reader(
                            owner_id, proposal.definition.task.task_id,
                        )
                    )
                    diagnoses = tuple(
                        item for item in evidence
                        if item.kind.value == "diagnosis"
                    )
                    task["failure_code"] = (
                        diagnoses[-1].conclusion_code if diagnoses
                        else "signed_postapply_verification_failed"
                    )
                    try:
                        task["rollback_checkpoint"] = self._rollback_checkpoint(
                            owner_id, proposal.definition.task.task_id,
                        )
                    except (
                        KeyError, PermissionError, RuntimeError, ValueError,
                    ) as error:
                        task["rollback_unavailable_reason"] = str(error)
        review_reader = getattr(self._loop, "reviews_for_task", None)
        reviews = () if review_reader is None else review_reader(
            owner_id, proposal.definition.task.task_id,
        )
        if reviews:
            task["reviews"] = [encode_document(item) for item in reviews]
            self._review_governance.attach_blocked(task, reviews)
        review_evidence_reader = getattr(
            self._loop, "review_evidence_for_task", None,
        )
        review_evidence = (
            () if review_evidence_reader is None else review_evidence_reader(
                owner_id, proposal.definition.task.task_id,
            )
        )
        if review_evidence:
            task["review_evidence"] = [
                encode_document(item) for item in review_evidence
            ]
        documentation_reader = getattr(self._loop, "documentation_for_task", None)
        documentation = (
            () if documentation_reader is None else documentation_reader(
                owner_id, proposal.definition.task.task_id,
            )
        )
        if documentation:
            task["documentation"] = [
                encode_document(item) for item in documentation
            ]
        diagnostic_request_reader = getattr(
            self._loop, "runtime_diagnostic_requests", None,
        )
        diagnostic_receipt_reader = getattr(
            self._loop, "runtime_diagnostic_receipts", None,
        )
        diagnostic_requests = (
            () if diagnostic_request_reader is None else
            diagnostic_request_reader(
                owner_id, proposal.definition.task.task_id,
            )
        )
        diagnostic_receipts = (
            () if diagnostic_receipt_reader is None else
            diagnostic_receipt_reader(
                owner_id, proposal.definition.task.task_id,
            )
        )
        if diagnostic_requests:
            task["runtime_diagnostic_requests"] = [
                encode_document(item) for item in diagnostic_requests
            ]
        if diagnostic_receipts:
            task["runtime_diagnostics"] = [
                encode_document(item) for item in diagnostic_receipts
            ]
            if task.get("stage") == "candidate_ready":
                passed = all(
                    item.status.value == "passed" for item in diagnostic_receipts
                )
                task["outcome"] = (
                    "runtime_diagnostics_completed" if passed
                    else "runtime_diagnostic_failed"
                )
                if not passed:
                    task["failure_code"] = "signed_runtime_diagnostic_failed"
        response["engineering_task"] = task
        return response

    def decline(self, owner_id: str, proposal_id: str) -> dict:
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        self._proposals.decline(proposal_id, "owner_declined")
        return self._view(proposal)

    def activate(
        self, owner_id: str, proposal_id: str, transport_session_id: str,
        *, confirmed: bool, goal_mode: bool = False,
    ) -> dict:
        self._require_owner(owner_id)
        if confirmed is not True:
            raise PermissionError("natural engineering activation requires confirmation")
        proposal = self._require_proposal(proposal_id)
        if proposal.grant.owner_id != owner_id:
            raise PermissionError("natural engineering proposal owner is invalid")
        allowed_separate = self._integration_authority.allowed_separate(
            proposal,
        )
        blocked = tuple(
            authority for authority in proposal.separately_confirmed_authorities
            if authority not in allowed_separate
        )
        if blocked:
            raise PermissionError(
                "request includes authorities requiring separate owner ceremonies"
            )
        if not self._proposals.begin_activation(proposal_id):
            status = self._proposals.status(proposal_id)
            raise PermissionError(
                "natural engineering proposal is already consumed"
                if status == "activated" else
                f"natural engineering proposal cannot activate from {status}"
            )
        try:
            prepared = self._start_or_resume(
                owner_id, proposal, transport_session_id,
            )
            if (
                self._executor is not None
                and EngineeringAuthority.MODIFY in proposal.definition.task.authorities
            ):
                prepared = self._executor.execute(
                    owner_id, proposal.definition,
                    session_id=transport_session_id, principal_id=owner_id,
                    **({"goal_mode": True} if goal_mode else {}),
                )
                if prepared.get("outcome") == "independent_review_blocked":
                    reviews = self._loop.reviews_for_task(
                        owner_id, proposal.definition.task.task_id,
                    )
                    self._review_governance.attach_blocked(prepared, reviews)
            elif (
                self._executor is not None
                and EngineeringAuthority.MODIFY
                not in proposal.definition.task.authorities
                and EngineeringAuthority.EXECUTE
                not in proposal.definition.task.authorities
            ):
                prepared = self._executor.answer(
                    owner_id, proposal.definition,
                    session_id=transport_session_id,
                )
            elif (
                self._executor is not None
                and EngineeringAuthority.EXECUTE in proposal.definition.task.authorities
                and self._loop.runtime_diagnostics_requested(
                    owner_id, proposal.definition.task.task_id,
                )
            ):
                prepared = self._executor.execute_diagnostics_only(
                    owner_id, proposal.definition,
                    session_id=transport_session_id, principal_id=owner_id,
                )
        except BaseException as error:
            logging.getLogger(__name__).exception(
                "Natural engineering activation failed for %s", proposal_id,
            )
            self._proposals.mark_interrupted(
                proposal_id, f"{type(error).__name__}:activation_interrupted",
            )
            raise
        if "outcome" not in prepared:
            prepared["outcome"] = "analysis_ready"
        self._attach_analysis_plan(
            prepared, proposal, transport_session_id,
        )
        if prepared.get("outcome", "").endswith("_failed"):
            self._proposals.mark_failed(
                proposal_id, prepared.get("failure_code") or "engineering_failed",
            )
        else:
            self._proposals.mark_activated(proposal_id)
        return {
            "proposal": self._view(proposal),
            "engineering_task": prepared,
        }

    def _attach_analysis_plan(self, task, proposal, transport_session_id) -> None:
        if task.get("outcome") != "analysis_ready":
            return
        reader = getattr(self._loop, "preparation", None)
        if reader is None:
            return
        preparation = reader(self.owner_id, proposal.definition.task.task_id)
        task["architecture_plan"] = architecture_plan_view(preparation.proposal)
        if self._conversation is None or not transport_session_id:
            return
        workspace_root = proposal.definition.task.workspace_roots[0]
        context = self._conversation.remember(
            self.owner_id, transport_session_id, workspace_root,
            preparation.proposal,
        )
        task["conversation_plan_reference"] = {
            "source_task_id": context.source_task_id,
            "workspace_root": context.workspace_root,
        }

    def approve_integration_resources(
        self, owner_id: str, proposal_id: str, transport_session_id: str,
        *, confirmed: bool,
    ) -> dict:
        """Activate one exact task-scoped network/opaque-secret grant."""
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        self._integration_authority.approve(
            owner_id, proposal, self._proposals.status(proposal_id),
            transport_session_id, confirmed=confirmed,
        )
        return {
            "proposal": self._view(proposal),
            "engineering_task": None,
        }

    def approve_changeset(
        self, owner_id: str, proposal_id: str, changeset_id: str,
        transport_session_id: str, *, confirmed: bool,
    ) -> dict:
        """Apply the exact displayed preview and reverify the owner workspace."""
        self._require_owner(owner_id)
        if confirmed is not True:
            raise PermissionError("natural engineering changeset requires confirmation")
        proposal = self._require_proposal(proposal_id)
        if (
            proposal.grant.owner_id != owner_id
            or self._proposals.status(proposal_id) != "activated"
        ):
            raise PermissionError("natural engineering proposal is not activated")
        task_id = proposal.definition.task.task_id
        changeset = self._exact_changeset(owner_id, task_id, changeset_id)
        decision = CheckpointDecision(
            f"decision-{changeset_id}", task_id, changeset_id, changeset_id,
            owner_id, self._clock(), CheckpointDisposition.APPROVED,
            candidate_preview_digest(changeset.preview),
            "Owner approved the exact Console changeset preview",
        )
        applied = self._loop.apply_candidate(
            owner_id, task_id, changeset_id, decision,
            session_id=transport_session_id, principal_id=owner_id,
        )
        integration_expected = bool(
            self._loop.inspect(owner_id, task_id).get(
                "integration_environment_receipt_ids",
            )
        )
        database_expected = bool(
            self._loop.database_results(owner_id, task_id)
        )
        verifications = []
        agent_reverification_id = None
        try:
            selected_recipes = self._loop.select_verification_recipes(
                owner_id, task_id,
            )
        except (LookupError, RuntimeError):
            if self._executor is None:
                raise
            try:
                agent_reverification_id = self._executor.reverify_agent(
                    owner_id, proposal.definition,
                )
            except LookupError:
                if not (database_expected or integration_expected):
                    raise
            selected_recipes = ()
        for index, (toolchain, recipe) in enumerate(selected_recipes):
            verifications.append(self._loop.reverify_candidate(
                owner_id, task_id,
                verification_id=f"postapply-{changeset_id}-{index}",
                session_id=transport_session_id, principal_id=owner_id,
                toolchain=toolchain, recipe_id=recipe.recipe_id,
                recipe_version=recipe.recipe_version,
                record_lifecycle=False,
            ))
        try:
            database_postapply = self._loop.reverify_database(
                owner_id, task_id, record_lifecycle=False,
            )
        except (LookupError, PermissionError, RuntimeError, ValueError):
            database_postapply = ()
        verification_passed = all(
            item.status is CandidateVerificationStatus.COMPLETED and item.passed
            for item in verifications
        )
        if not verifications:
            verification_passed = (
                agent_reverification_id is not None
                or database_expected
                or integration_expected
            )
        database_passed = (
            (not database_expected)
            or bool(database_postapply) and all(
                item.passed for item in database_postapply
            )
        )
        passed = verification_passed and database_passed
        diagnostic_requests = diagnostic_receipts = ()
        diagnostics_passed = True
        if passed and self._executor is not None:
            try:
                diagnostic_requests, diagnostic_receipts = (
                    self._executor.reverify_diagnostics(
                        owner_id, proposal.definition,
                        session_id=transport_session_id,
                        principal_id=owner_id,
                    )
                )
                diagnostics_passed = all(
                    item.status.value == "passed" for item in diagnostic_receipts
                )
            except (LookupError, PermissionError, RuntimeError, ValueError):
                diagnostics_passed = False
            passed = passed and diagnostics_passed
        integration = None
        integration_passed = not integration_expected
        if passed and integration_expected:
            if self._executor is not None:
                try:
                    integration = self._executor.reverify_integration(
                        owner_id, proposal.definition, changeset_id,
                        session_id=transport_session_id,
                        principal_id=owner_id,
                    )
                    integration_passed = (
                        integration is not None
                        and integration.cleanup_receipt.status.value == "cleaned"
                        and (
                            integration.postgresql_plan is None
                            and integration.postgresql_verification is None
                            or integration.postgresql_plan is not None
                            and integration.postgresql_verification is not None
                            and integration.postgresql_verification.passed
                        )
                    )
                except (
                    LookupError, OSError, PermissionError, RuntimeError,
                    ValueError,
                ):
                    integration_passed = False
            passed = passed and integration_passed
        if passed:
            if database_postapply:
                self._loop.accept_database_postapply(
                    owner_id, task_id, database_postapply,
                )
            if verifications:
                self._loop.accept_postapply_verifications(
                    owner_id, task_id, verifications,
                )
            recovered_incident = self._incidents.complete_task_recovery(
                owner_id, task_id,
                (
                    *(item.verification_id for item in verifications),
                    *((agent_reverification_id,) if agent_reverification_id else ()),
                    *(item.receipt_id for item in database_postapply),
                    *(() if integration is None else (
                        integration.cleanup_receipt.receipt_id,
                        *(() if integration.postgresql_verification is None else (
                            integration.postgresql_verification.receipt_id,
                        )),
                    )),
                ),
            )
        else:
            recovered_incident = None
        response = self._loop.inspect(owner_id, task_id)
        delivery = None
        if (
            passed
            and EngineeringOperation.GIT_WRITE
            in proposal.definition.task.permitted_operations
        ):
            delivery = self._loop.commit_candidate(
                owner_id, task_id, changeset_id,
                session_id=transport_session_id, principal_id=owner_id,
                message=_commit_message(proposal.definition.task.intent),
            )
            response = self._loop.inspect(owner_id, task_id)
        response.update({
            "outcome": (
                "local_commit_completed" if passed and delivery is not None
                else "reverification_completed" if passed
                else "postapply_verification_failed"
            ),
            "changeset": encode_document(applied),
            "postapply_verifications": [
                encode_document(item) for item in verifications
            ],
            "postapply_agent_verification_id": agent_reverification_id,
            "postapply_runtime_diagnostic_requests": [
                encode_document(item) for item in diagnostic_requests
            ],
            "postapply_runtime_diagnostics": [
                encode_document(item) for item in diagnostic_receipts
            ],
            "postapply_database_receipts": [
                encode_document(item) for item in database_postapply
            ],
            "postapply_integration_environment": (
                None if integration is None else {
                    "plan": encode_document(integration.plan),
                    "start_result": encode_document(integration.start_result),
                    "cleanup_receipt": encode_document(
                        integration.cleanup_receipt
                    ),
                    "postgresql_plan": (
                        None if integration.postgresql_plan is None else
                        encode_document(integration.postgresql_plan)
                    ),
                    "postgresql_verification": (
                        None if integration.postgresql_verification is None else
                        encode_document(integration.postgresql_verification)
                    ),
                }
            ),
        })
        if delivery is not None:
            response["git_delivery"] = encode_document(delivery)
            self._attach_rollback_checkpoint(response, owner_id, task_id)
            self._publication.attach(
                response, proposal, create=True, changeset_id=changeset_id,
            )
        if recovered_incident is not None:
            self._incidents.attach(
                response, owner_id, task_id, recovered_incident,
            )
        if not passed:
            response["failure_code"] = (
                "signed_postapply_verification_failed"
                if not verification_passed else
                "database_postapply_verification_failed"
                if not database_passed else
                "signed_postapply_runtime_diagnostic_failed"
                if not diagnostics_passed else
                "signed_postapply_integration_environment_failed"
            )
            incident = self._loop.record_incident(
                owner_id, task_id, response["failure_code"],
                (
                    *(item.verification_id for item in verifications),
                    *(item.receipt_id for item in database_postapply),
                    *(() if integration is None else (
                        integration.cleanup_receipt.receipt_id,
                        *(() if integration.postgresql_verification is None else (
                            integration.postgresql_verification.receipt_id,
                        )),
                    )),
                ),
            )
            if incident is not None:
                try:
                    checkpoint = self._loop.rollback_checkpoint(
                        owner_id, task_id, changeset_id,
                    )
                except (KeyError, PermissionError, RuntimeError, ValueError) as error:
                    checkpoint = None
                    response["rollback_unavailable_reason"] = str(error)
                if checkpoint is not None:
                    incident = self._incidents.propose_rollback(
                        owner_id, incident, checkpoint,
                    )
                    response["rollback_checkpoint"] = checkpoint
                self._incidents.attach(
                    response, owner_id, task_id, incident,
                )
        return {"proposal": self._view(proposal), "engineering_task": response}

    def approve_publication(
        self, owner_id: str, proposal_id: str, publication_proposal_id: str,
        transport_session_id: str, *, confirmed: bool,
    ) -> dict:
        """Activate one separate exact publish grant and consume its proposal."""
        self._require_owner(owner_id)
        proposal = self._require_proposal(proposal_id)
        if (
            proposal.grant.owner_id != owner_id
            or self._proposals.status(proposal_id) != "activated"
        ):
            raise PermissionError("natural engineering proposal is not activated")
        response = self._publication.approve(
            owner_id, proposal, publication_proposal_id,
            transport_session_id, confirmed=confirmed,
        )
        return {"proposal": self._view(proposal), "engineering_task": response}

    def waive_review(
        self, owner_id: str, proposal_id: str, checkpoint_id: str,
        finding_id: str, consequences_sha256: str,
        transport_session_id: str, *, confirmed: bool,
    ) -> dict:
        """Explicitly waive one exact finding with owner-authenticated reduced assurance."""
        self._require_owner(owner_id)
        if confirmed is not True:
            raise PermissionError("engineering review waiver requires confirmation")
        proposal = self._require_proposal(proposal_id)
        if (
            proposal.grant.owner_id != owner_id
            or self._proposals.status(proposal_id) != "activated"
        ):
            raise PermissionError("natural engineering proposal is not activated")
        task_id = proposal.definition.task.task_id
        prior, updated = self._review_governance.waive(
            owner_id, task_id, checkpoint_id, finding_id,
            consequences_sha256, transport_session_id,
        )
        response = self.progress(owner_id, proposal_id)
        response["engineering_task"]["review_waiver"] = encode_document(prior)
        response["engineering_task"]["review"] = encode_document(updated)
        return response

    def rollback(
        self, owner_id: str, proposal_id: str, rollback_id: str,
        transport_session_id: str, *, confirmed: bool,
    ) -> dict:
        """Execute the exact displayed rollback and preserve Git history."""
        self._require_owner(owner_id)
        if confirmed is not True:
            raise PermissionError("natural engineering rollback requires confirmation")
        proposal = self._require_proposal(proposal_id)
        if (
            proposal.grant.owner_id != owner_id
            or self._proposals.status(proposal_id) != "activated"
        ):
            raise PermissionError("natural engineering proposal is not activated")
        task_id = proposal.definition.task.task_id
        checkpoint = self._rollback_checkpoint(owner_id, task_id)
        if checkpoint["rollback_id"] != rollback_id:
            raise PermissionError("natural engineering rollback checkpoint changed")
        changeset_id = checkpoint["changeset_id"]
        record = self._changeset_by_id(owner_id, task_id, changeset_id)
        decision = record.rollback_decision or CheckpointDecision(
            f"decision-{rollback_id}", task_id, rollback_id, rollback_id,
            owner_id, self._clock(), CheckpointDisposition.APPROVED,
            checkpoint["approval_sha256"],
            "Owner approved the exact history-preserving rollback",
        )
        changeset, delivery = self._loop.rollback_candidate(
            owner_id, task_id, changeset_id, decision,
            session_id=transport_session_id, principal_id=owner_id,
            expected_head_object_id=checkpoint["expected_head_object_id"],
            message=f"FAM rollback: {_commit_message(proposal.definition.task.intent)[5:]}",
        )
        response = self._loop.inspect(owner_id, task_id)
        completed = (
            changeset.status.value == "explicitly_rolled_back"
            and response.get("stage") == "rolled_back"
        )
        response.update({
            "outcome": (
                "rollback_completed" if completed
                else "rollback_recovery_required"
            ),
            "rollback_changeset": encode_document(changeset),
            "rollback_checkpoint": checkpoint,
        })
        if delivery is not None:
            response["git_rollback_delivery"] = encode_document(delivery)
        if completed:
            incident = self._incidents.complete_rollback(
                owner_id, task_id, changeset,
            )
            self._incidents.attach(
                response, owner_id, task_id, incident,
            )
        if not completed:
            response["failure_code"] = "explicit_rollback_incomplete"
        return {"proposal": self._view(proposal), "engineering_task": response}

    def close(self) -> None:
        if self._executor is not None:
            self._executor.close()
        self._proposals.close()

    def _require_owner(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            raise PermissionError("natural engineering owner is invalid")

    def _require_proposal(self, proposal_id: str):
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise KeyError("natural engineering proposal is unavailable")
        return proposal


    def _exact_changeset(self, owner_id, task_id, changeset_id):
        matches = tuple(
            item for item in self._loop.candidate_changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if len(matches) != 1:
            raise KeyError("natural engineering changeset is unavailable")
        state = self._loop.inspect(owner_id, task_id)
        record = matches[0]
        applied_retry = (
            state.get("stage") in {"applied", "reverified", "committed", "completed"}
            and record.status.value == "applied"
        )
        if state.get("diff_checkpoint_id") != changeset_id and not applied_retry:
            raise PermissionError("natural engineering changeset is not the pending checkpoint")
        return record

    def _rollback_checkpoint(self, owner_id, task_id):
        candidates = sorted(
            self._loop.candidate_changesets(owner_id, task_id),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        failures = []
        for record in candidates:
            try:
                return self._loop.rollback_checkpoint(
                    owner_id, task_id, record.changeset_id,
                )
            except (PermissionError, RuntimeError, ValueError) as error:
                failures.append(str(error))
        detail = failures[0] if failures else "no applied changeset"
        raise KeyError(f"natural engineering rollback is unavailable: {detail}")

    def _changeset_by_id(self, owner_id, task_id, changeset_id):
        values = tuple(
            item for item in self._loop.candidate_changesets(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if len(values) != 1:
            raise KeyError("natural engineering rollback changeset is unavailable")
        return values[0]

    def _attach_rollback_checkpoint(self, response, owner_id, task_id):
        try:
            response["rollback_checkpoint"] = self._rollback_checkpoint(
                owner_id, task_id,
            )
        except KeyError as error:
            response["rollback_unavailable_reason"] = str(error)

    def _start_or_resume(self, owner_id, proposal, transport_session_id):
        task_id = proposal.definition.task.task_id
        try:
            self._loop.inspect(owner_id, task_id)
        except (AttributeError, KeyError):
            try:
                self._loop.start(owner_id, proposal.definition, proposal.budget)
            except PermissionError:
                self._activate_grant(owner_id, proposal, transport_session_id)
                self._loop.start(owner_id, proposal.definition, proposal.budget)
        try:
            return self._loop.prepare(owner_id, task_id)
        except PermissionError:
            self._activate_grant(owner_id, proposal, transport_session_id)
            return self._loop.prepare(owner_id, task_id)

    def _activate_grant(self, owner_id, proposal, transport_session_id):
        self._activate_grant_document(
            owner_id, proposal.grant, transport_session_id,
            purpose="engineering-grant",
        )

    def _activate_grant_document(
        self, owner_id, grant, transport_session_id, *, purpose,
    ):
        digest = engineering_grant_digest(grant)
        context = self._authentication.issue(
            owner_id, purpose, digest,
            transport_session_id=transport_session_id,
        )
        if not self._authentication.belongs_to_session(
            context.context_id, transport_session_id,
        ):
            raise PermissionError("engineering authentication session binding failed")
        approval = OwnerGrantApproval(
            f"approval-{grant.grant_id}", grant.grant_id,
            owner_id, digest, self._clock(), context.context_id,
        )
        challenge = decision = None
        if grant.requires_break_glass:
            issued = self._clock()
            consequences = (
                "Commands run with the current OS user's host filesystem and process access.",
                "Host commands are not isolated by the Workspace sandbox.",
                "The model may modify resources outside the selected repository when required by the task.",
            )
            consequence_sha = consequences_digest(consequences)
            challenge = BreakGlassChallenge(
                f"break-glass-challenge-{grant.grant_id}", owner_id,
                grant.grant_id, grant.authorities, grant.verification,
                grant.scope.kind, grant.scope.scope_id, consequences,
                consequence_sha, issued, min(grant.expires_at, issued + timedelta(minutes=2)),
            )
            decision = BreakGlassDecision(
                grant.break_glass_decision_id, challenge.challenge_id,
                owner_id, grant.grant_id, BreakGlassDisposition.APPROVED,
                grant.scope.kind, grant.scope.scope_id, consequence_sha,
                issued, "pending-break-glass-context",
            )
            break_context = self._authentication.issue(
                owner_id, "engineering-break-glass",
                break_glass_authentication_digest(challenge, decision),
                transport_session_id=transport_session_id,
            )
            decision = replace(
                decision, authentication_context_id=break_context.context_id,
            )
        if challenge is None or decision is None:
            self._authorizer.activate(grant, approval)
        else:
            self._authorizer.activate(grant, approval, challenge, decision)

    def _view(self, proposal):
        value = _view(proposal, self._proposals.status(proposal.proposal_id))
        self._integration_authority.attach(value, proposal)
        failure = self._proposals.failure(proposal.proposal_id)
        if failure is not None:
            value["failure_code"] = failure
        return value



def _toolchains(evidence) -> tuple[str, ...]:
    values = []
    manifest_map = {
        "python": "python3", "node": "node", "rust": "rust",
        "go": "go", "java": "java",
    }
    for manifest in evidence.manifests:
        value = manifest_map.get(manifest.ecosystem)
        if value is not None:
            values.append(value)
    if values:
        return tuple(dict.fromkeys(values))
    language_map = {
        "python": "python3", "javascript": "node", "typescript": "node",
        "rust": "rust", "go": "go", "java": "java", "csharp": "dotnet",
        "c": "gcc", "cpp": "g++", "shell": "bash",
        "html": "html", "css": "css",
    }
    for item in evidence.files:
        value = language_map.get(item.language)
        if value is not None:
            values.append(value)
    return tuple(dict.fromkeys(values))


def _commit_message(intent: str) -> str:
    normalized = " ".join(intent.split())
    return "FAM: " + normalized[:200]


def _database_result_view(result) -> dict:
    return {
        "plan": encode_document(result.plan),
        "backup": (
            None if result.backup is None else encode_document(result.backup)
        ),
        "verification": encode_document(result.verification),
        "backup_relative_path": result.backup_relative_path,
        "failure_code": result.failure_code,
    }


def _integration_environment_view(stored) -> dict:
    return {
        "state": stored.state,
        "plan": encode_document(stored.plan),
        "candidate": encode_document(stored.candidate),
        "start_result": encode_document(stored.start_result),
        "latest_receipt": encode_document(stored.latest_receipt),
    }


def _view(proposal, status) -> dict:
    return {
        "proposal_id": proposal.proposal_id,
        "status": status,
        "prompt_sha256": proposal.prompt_sha256,
        "grant": encode_document(proposal.grant),
        "definition": encode_document(proposal.definition),
        "budget": {
            name: getattr(proposal.budget, name)
            for name in (
                "maximum_tokens", "maximum_wall_seconds", "maximum_commands",
                "maximum_network_bytes", "maximum_files", "maximum_storage_bytes",
            )
        },
        "separately_confirmed_authorities": [
            item.value for item in proposal.separately_confirmed_authorities
        ],
    }
