import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from fam_os.core.lifecycle import GlobalAttemptBudget
from fam_os.core.ports import InferenceResponse
from fam_os.core.production import (
    InferenceExecutionState,
    ModelIntent,
    RuntimeModelEntry,
)
from fam_os.core.production.gateway import ProductionTaskGateway
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import HostCapacity, ResourceAwareModelSelector
from fam_os.fabric import (
    PeerManagementOperation,
    PeerManagementRequest,
    RemoteContextSensitivity,
    RemoteExecutionAuthority,
    RemoteEvidenceDisposition,
    RemoteAttemptFailure,
    RemoteRecoveryDisposition,
    RemotePrivacyPolicy,
    RemoteVerificationOutcome,
    create_capability_declaration,
)
from fam_os.product.composition.peer_service import ProductPeerService, ProductPeerSettings
from fam_os.product.peer_context import ProductPeerContextService
from fam_os.product.peer_management import ProductPeerManagement
from fam_os.product.remote_execution_client import ProductRemoteExecutionClient
from fam_os.product.remote_execution_planner import ProductRemoteExecutionPlanner
from fam_os.product.remote_execution_server import ProductRemoteExecutionServer
from fam_os.product.verified_outcome_learning import ProductVerifiedOutcomeLearning
from fam_os.shell import ShellAskCommand, ShellRunState
from fam_os.telemetry import InferenceMetrics
from tests.integration.test_product_peer_management import (
    _approvals,
    _storage,
    _unused_port,
)


class ProductRemoteExecutionTests(unittest.TestCase):
    def test_remote_candidate_runs_through_normal_core_verifier(self):
        with _environment("READY", "LOCAL MUST NOT RUN") as value:
            accepted = value.gateway.ask(_command(value, "remote-core-request"))
            terminal = _terminal(value.gateway, accepted.session_id)

            self.assertTrue(terminal.result.verified)
            self.assertEqual("READY", terminal.result.content)
            self.assertEqual([], value.local_runtime.requests)
            self.assertEqual(1, len(value.remote_runtime.requests))
            self.assertEqual("test:q4", value.remote_runtime.requests[0].model_ref)
            record = value.repositories.inference_executions.get(accepted.session_id)
            self.assertTrue(record.remote_attempt_consumed)
            self.assertEqual("test:q4", record.selection.model_ref)
            self.assertEqual("economical", record.selection.tier)
            self.assertEqual(1, len(value.repositories.peer_context.all()))
            self.assertEqual(1, len(value.server_repositories.peer_context.all()))
            self.assertEqual(value.peer.device_id, record.remote_plan.peer_device_id)
            learned = value.outcomes.records()
            self.assertEqual(1, len(learned))
            self.assertEqual("economical", learned[0].expert_tier)
            evidence = value.repositories.final_evidence.remote_execution_for_request(
                "remote-core-request",
            )
            self.assertEqual(RemoteEvidenceDisposition.RELEASED, evidence.disposition)
            self.assertEqual(RemoteVerificationOutcome.PASSED, evidence.verification_outcome)
            self.assertEqual(record.candidate_id, evidence.candidate_id)
            self.assertEqual(terminal.result.evidence_ids[1], evidence.acceptance_evidence_id)
            self.assertIn(evidence.evidence_id, terminal.result.evidence_ids)
            self.assertFalse(evidence.raw_content_retained)
            self.assertFalse(evidence.partial_output_retained)

    def test_failed_remote_verification_repairs_locally_under_one_budget(self):
        with _environment("WRONG", "READY") as value:
            accepted = value.gateway.ask(_command(value, "remote-repair-request"))
            terminal = _terminal(value.gateway, accepted.session_id)

            self.assertTrue(terminal.result.verified)
            self.assertEqual("READY", terminal.result.content)
            self.assertEqual(1, len(value.remote_runtime.requests))
            self.assertEqual(1, len(value.local_runtime.requests))
            self.assertEqual("local:q4", value.local_runtime.requests[0].model_ref)
            record = value.repositories.inference_executions.get(accepted.session_id)
            self.assertTrue(record.remote_attempt_consumed)
            self.assertEqual("local:q4", record.selection.model_ref)
            budget = value.storage.core.budget_ledger(GlobalAttemptBudget(
                accepted.session_id, 4096, 720_000, 1, 2,
            )).snapshot()
            self.assertEqual(1, budget.repairs)
            self.assertEqual(2048, budget.consumed_tokens)
            self.assertEqual(360_000, budget.consumed_wall_milliseconds)
            self.assertEqual(2, len(budget.reservation_ids))
            evidence = value.repositories.final_evidence.remote_execution_for_request(
                "remote-repair-request",
            )
            self.assertEqual(RemoteEvidenceDisposition.REJECTED, evidence.disposition)
            self.assertEqual(RemoteVerificationOutcome.FAILED, evidence.verification_outcome)
            self.assertIsNone(evidence.acceptance_evidence_id)

    def test_privacy_revision_change_after_admission_fails_before_network(self):
        with _environment("READY", "LOCAL MUST NOT RUN") as value:
            accepted = value.gateway.ask(_command(value, "remote-stale-policy"))
            value.peers.apply_control(PeerManagementRequest(
                "remote-privacy-revision-2", str(os.geteuid()),
                PeerManagementOperation.SET_PRIVACY,
                value.enrollment.enrollment_id, 1, True,
                "owner.scope-changed",
                RemotePrivacyPolicy(
                    str(os.geteuid()), (value.server_device_id,),
                    ("assist",), ("workspace:test",), 8192,
                    (RemoteContextSensitivity.PRIVATE,), True,
                ),
            ))
            terminal = _terminal(value.gateway, accepted.session_id)

            self.assertFalse(terminal.result.verified)
            self.assertIsNone(terminal.result.content)
            self.assertEqual([], value.remote_runtime.requests)
            self.assertEqual([], value.local_runtime.requests)
            self.assertEqual((), value.repositories.peer_context.all())
            record = value.repositories.inference_executions.get(accepted.session_id)
            self.assertEqual(
                "fabric.remote_recovery.denied", record.failure_code,
            )
            self.assertIsNone(
                value.repositories.final_evidence.remote_execution_for_request(
                    "remote-stale-policy",
                ),
            )
            recovery = value.repositories.final_evidence.remote_recovery_for_request(
                "remote-stale-policy",
            )
            self.assertEqual(
                RemoteAttemptFailure.AUTHORITY_CHANGED, recovery.failure,
            )
            self.assertEqual(
                RemoteRecoveryDisposition.RETRY_DENIED, recovery.disposition,
            )

    def test_truncated_peer_output_is_discarded_before_bounded_local_recovery(self):
        def factory(_trust):
            return _TruncatedPeerClient()

        with _environment(
            "REMOTE MUST NOT RUN", "READY", client_factory=factory,
        ) as value:
            accepted = value.gateway.ask(_command(value, "remote-truncated-frame"))
            terminal = _terminal(value.gateway, accepted.session_id)

            self.assertTrue(terminal.result.verified)
            self.assertEqual("READY", terminal.result.content)
            self.assertEqual([], value.remote_runtime.requests)
            self.assertEqual(1, len(value.local_runtime.requests))
            self.assertIsNone(
                value.repositories.final_evidence.remote_execution_for_request(
                    "remote-truncated-frame",
                ),
            )
            recovery = value.repositories.final_evidence.remote_recovery_for_request(
                "remote-truncated-frame",
            )
            self.assertEqual(RemoteAttemptFailure.PARTIAL_RESULT, recovery.failure)
            self.assertEqual(RemoteRecoveryDisposition.RECOVERED, recovery.disposition)
            self.assertTrue(recovery.unchanged_acceptance)
            self.assertEqual(terminal.result.evidence_ids[-1], recovery.evidence_id)
            budget = value.storage.core.budget_ledger(GlobalAttemptBudget(
                accepted.session_id, 4096, 720_000, 1, 2,
            )).snapshot()
            self.assertEqual(2048, budget.consumed_tokens)
            self.assertEqual(600_000, budget.consumed_wall_milliseconds)
            connection = sqlite3.connect(value.desktop_root / "state/fam.sqlite3")
            try:
                count = connection.execute(
                    "SELECT count(*) FROM final_evidence "
                    "WHERE request_id=? AND evidence_kind='remote_execution'",
                    ("remote-truncated-frame",),
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(0, count)
            self.assertFalse(any(
                _TruncatedPeerClient.PARTIAL in path.read_bytes()
                for path in (value.desktop_root / "state").glob("fam.sqlite3*")
            ))

    def test_restart_reconciles_uncertain_remote_attempt_once_before_local_retry(self):
        def factory(_trust):
            return _CrashPeerClient()

        with _environment(
            "REMOTE MUST NOT COMPLETE", "READY", client_factory=factory,
        ) as value:
            accepted = value.gateway.ask(_command(value, "remote-restart-loss"))
            record = value.repositories.inference_executions.get(accepted.session_id)
            with self.assertRaises(_SimulatedProcessLoss):
                value.gateway._execution.generate_candidate(record)

            interrupted = value.repositories.inference_executions.get(
                accepted.session_id,
            )
            self.assertEqual(InferenceExecutionState.RUNNING, interrupted.state)
            self.assertTrue(interrupted.remote_attempt_consumed)
            before = value.storage.core.budget_ledger(GlobalAttemptBudget(
                accepted.session_id, 4096, 720_000, 1, 2,
            )).snapshot()
            self.assertEqual(1, len(before.reservation_ids))

            resumed = ProductionTaskGateway(
                value.local_runtime, value.repositories,
                value.selector, value.capacity,
                value.storage.core.budget_ledger,
            )
            terminal = _terminal(resumed, accepted.session_id)

            self.assertTrue(terminal.result.verified)
            self.assertEqual("READY", terminal.result.content)
            self.assertEqual(1, len(value.local_runtime.requests))
            recovery = value.repositories.final_evidence.remote_recovery_for_request(
                "remote-restart-loss",
            )
            self.assertEqual(
                RemoteAttemptFailure.UNCERTAIN_COMPLETION, recovery.failure,
            )
            self.assertEqual(RemoteRecoveryDisposition.RECOVERED, recovery.disposition)
            after = value.storage.core.budget_ledger(GlobalAttemptBudget(
                accepted.session_id, 4096, 720_000, 1, 2,
            )).snapshot()
            self.assertEqual(2, len(after.reservation_ids))

    def test_restart_reconciles_authenticated_candidate_without_reexecuting_peer(self):
        with _environment("READY", "LOCAL MUST NOT RUN") as value:
            accepted = value.gateway.ask(_command(value, "remote-candidate-restart"))
            repository = value.repositories.inference_executions
            original_replace = repository.replace

            def crash_before_candidate_state(expected_revision, updated):
                if updated.state is InferenceExecutionState.CANDIDATE_READY:
                    raise _SimulatedProcessLoss(
                        "process stopped after atomic candidate persistence",
                    )
                return original_replace(expected_revision, updated)

            repository.replace = crash_before_candidate_state
            try:
                record = repository.get(accepted.session_id)
                with self.assertRaises(_SimulatedProcessLoss):
                    value.gateway._execution.generate_candidate(record)
            finally:
                repository.replace = original_replace

            interrupted = repository.get(accepted.session_id)
            self.assertEqual(InferenceExecutionState.RUNNING, interrupted.state)
            pending = value.repositories.final_evidence.remote_execution_for_request(
                "remote-candidate-restart",
            )
            self.assertEqual(
                RemoteEvidenceDisposition.AUTHENTICATED_CANDIDATE,
                pending.disposition,
            )

            resumed = ProductionTaskGateway(
                value.local_runtime, value.repositories,
                value.selector, value.capacity,
                value.storage.core.budget_ledger,
            )
            terminal = _terminal(resumed, accepted.session_id)

            self.assertTrue(terminal.result.verified)
            self.assertEqual("READY", terminal.result.content)
            self.assertEqual(1, len(value.remote_runtime.requests))
            self.assertEqual([], value.local_runtime.requests)
            finalized = value.repositories.final_evidence.remote_execution_for_request(
                "remote-candidate-restart",
            )
            self.assertEqual(RemoteEvidenceDisposition.RELEASED, finalized.disposition)


def _command(value, request_id):
    return ShellAskCommand(
        request_id, "Reply with exactly READY", verification_required=True,
        remote_authority=RemoteExecutionAuthority(
            value.enrollment.enrollment_id, 1, "assist", "workspace:test",
            RemoteContextSensitivity.PRIVATE, 8192, 4096, True,
        ),
    )


@contextmanager
def _environment(remote_content, local_content, *, client_factory=None):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        server_root, desktop_root = root / "server", root / "desktop"
        port = _unused_port()
        server_credentials, _, server_approval, desktop_approval = _approvals(
            server_root, desktop_root, port,
        )
        server_storage, server_repositories = _storage(server_root)
        desktop_storage, desktop_repositories = _storage(desktop_root)
        server_repositories.peer_enrollments.enroll(server_approval)
        desktop_enrollment = desktop_repositories.peer_enrollments.enroll(
            desktop_approval,
        )
        remote_runtime = _Runtime(remote_content)
        local_runtime = _Runtime(local_content)
        server = ProductPeerService(
            ProductPeerSettings(server_root, "Server", "127.0.0.1", port),
            server_repositories.peer_enrollments, os.geteuid(), _capabilities,
            server_repositories.peer_context,
            ProductRemoteExecutionServer(remote_runtime, _capabilities),
        )
        desktop = ProductPeerService(
            ProductPeerSettings(desktop_root, "Desktop"),
            desktop_repositories.peer_enrollments, os.geteuid(),
            context_repository=desktop_repositories.peer_context,
        )
        try:
            server.start()
            desktop.start()
            context = ProductPeerContextService(
                desktop_repositories.peer_enrollments,
                desktop_repositories.peer_state,
                desktop_repositories.peer_context,
                desktop, str(os.geteuid()),
            )
            peers = ProductPeerManagement(
                desktop_repositories.peer_enrollments,
                desktop_repositories.peer_state,
                desktop, str(os.geteuid()), context=context,
            )
            peer = peers.probe(desktop_enrollment.enrollment_id, "remote-probe")
            peers.apply_control(PeerManagementRequest(
                "remote-privacy", str(os.geteuid()),
                PeerManagementOperation.SET_PRIVACY,
                desktop_enrollment.enrollment_id, 0, True,
                "owner.remote-execution",
                RemotePrivacyPolicy(
                    str(os.geteuid()), (server_credentials.identity.device_id,),
                    ("assist",), ("workspace:test",), 8192,
                    (RemoteContextSensitivity.PRIVATE,), True,
                ),
            ))
            executor = ProductRemoteExecutionClient(
                context, desktop_repositories.peer_enrollments,
                desktop, str(os.geteuid()),
                client_factory=client_factory,
            )
            catalog = RuntimeModelCatalog((RuntimeModelEntry(
                "local:q4", "economical", tuple(ModelIntent), 1024**3,
                8192, "b" * 64, ("verifier.text.exact-v1",),
            ),))
            outcomes = ProductVerifiedOutcomeLearning(desktop_repositories)
            selector = ResourceAwareModelSelector(catalog)

            def capacity():
                return HostCapacity(16 * 1024**3)

            gateway = ProductionTaskGateway(
                local_runtime, desktop_repositories,
                selector,
                capacity,
                desktop_storage.core.budget_ledger,
                remote_planner=ProductRemoteExecutionPlanner(peers),
                remote_executor=executor, outcomes=outcomes,
            )
            yield SimpleNamespace(
                gateway=gateway, local_runtime=local_runtime,
                remote_runtime=remote_runtime, repositories=desktop_repositories,
                server_repositories=server_repositories, storage=desktop_storage,
                enrollment=desktop_enrollment, peer=peer, peers=peers,
                server_device_id=server_credentials.identity.device_id,
                executor=executor, outcomes=outcomes,
                desktop_root=desktop_root,
                selector=selector, capacity=capacity,
            )
        finally:
            desktop.stop()
            server.stop()
            desktop_storage.stop()
            server_storage.stop()


class _Runtime:
    def __init__(self, content):
        self.content = content
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return InferenceResponse(
            self.content,
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 2, 200.0),
        )

    def loaded_models(self):
        return ()


class _TruncatedPeerClient:
    PARTIAL = b"PARTIAL_REMOTE_OUTPUT_MUST_NEVER_PERSIST"

    def request(self, _device_id, _payload):
        raise EOFError(self.PARTIAL.decode("ascii"))


class _SimulatedProcessLoss(BaseException):
    pass


class _CrashPeerClient:
    def request(self, _device_id, _payload):
        raise _SimulatedProcessLoss("process stopped after the remote attempt began")


def _capabilities(credentials, observed_at):
    revision = max(1, int(observed_at.timestamp() * 1_000_000))
    return (create_capability_declaration(
        credentials, declaration_id=f"capability-{revision}",
        expert_id="expert.conversation", model_ref="test:q4",
        expert_tier="economical",
        capability_ids=("language.generate",), maximum_context_bytes=8192,
        manifest_sha256="a" * 64, revision=revision, issued_at=observed_at,
        expires_at=observed_at + timedelta(hours=1),
    ),)


def _terminal(gateway, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = gateway.snapshot(session_id)
        if value.state is ShellRunState.TERMINAL:
            return value
        time.sleep(0.01)
    raise AssertionError("remote task did not become terminal")


if __name__ == "__main__":
    unittest.main()
