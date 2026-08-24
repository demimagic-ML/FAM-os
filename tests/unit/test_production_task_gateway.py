import hashlib
import json
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fam_os.core.contracts import ResultStatus, StepOutcome
from fam_os.core.lifecycle import PlanLifecycleService
from fam_os.core.ports import InferenceResponse
from fam_os.core.production import (
    ModelIntent,
    RuntimeModelEntry,
)
from fam_os.core.production.gateway import ProductionTaskGateway
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import HostCapacity, ResourceAwareModelSelector
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.composition.verifier_unit import production_verifier
from fam_os.product.verified_outcome_learning import ProductVerifiedOutcomeLearning
from fam_os.product.storage.terminal_redaction import TERMINAL_CONTENT_REDACTION
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)
from fam_os.memory import ProductionSessionMemory
from fam_os.shell import ShellAskCommand, ShellRunState
from fam_os.shell import ShellVerifiedAskCommand
from fam_os.telemetry import InferenceMetrics
from fam_os.schemas import dumps_document
from fam_os.fabric import RemoteContextSensitivity, RemoteExecutionAuthority
from fam_os.verification import (
    ExactTextVerification,
    RetrievalCitationsVerification,
    RetrievedSource,
    VerificationDeclaration,
    contract_for_kind,
    retrieval_query_obligation,
)


class ProductionTaskGatewayTests(unittest.TestCase):
    def test_terminal_plan_with_unfinished_worker_is_reconciled_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            gateway = _gateway(resources, _Runtime("must not run"))
            accepted = gateway.ask(ShellAskCommand(
                "terminal-gap", "Exercise the terminal reconciliation gap",
            ))
            snapshot = resources.repositories.plans.get(accepted.session_id)
            advanced = PlanLifecycleService(resources.repositories.plans).advance(
                accepted.session_id, snapshot.revision, StepOutcome.FAILED,
            )
            self.assertIsNone(advanced.rejection)
            self.assertTrue(advanced.snapshot.terminal)
            gateway._run_worker = lambda _instance_id: None

            result = gateway.snapshot(accepted.session_id)

            self.assertEqual(ShellRunState.TERMINAL, result.state)
            self.assertEqual(ResultStatus.FAILED, result.result.status)
            self.assertNotEqual("Finalizing durable evidence", result.message)
            execution = resources.repositories.inference_executions.get(
                accepted.session_id,
            )
            self.assertEqual("terminal", execution.state.value)
            self.assertEqual("core.worker.failed", execution.failure_code)
            resources.database.close()

    def test_explicit_remote_authority_fails_closed_without_bound_fabric(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            gateway = _gateway(resources, _Runtime("must not run"))
            with self.assertRaisesRegex(PermissionError, "remote execution is unavailable"):
                gateway.ask(ShellAskCommand(
                    "remote-unavailable", "Use a remote model",
                    remote_authority=RemoteExecutionAuthority(
                        "enrollment", 1, "assist", "workspace:test",
                        RemoteContextSensitivity.PRIVATE, 4096, 4096, True,
                    ),
                ))
            self.assertIsNone(resources.requests.get("remote-unavailable"))
            resources.database.close()

    def test_live_context_advice_reaches_the_normal_inference_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            runtime = _Runtime("adapted response")
            adaptation = _Adaptation()
            gateway = _gateway(resources, runtime, adaptation=adaptation)

            accepted = gateway.ask(ShellAskCommand(
                "adapted-context", "Describe the repeated local workflow",
            ))
            _terminal(gateway, accepted.session_id)

            self.assertEqual([4096], runtime.contexts)
            self.assertEqual("adapted-context", adaptation.request_ids[0])
            resources.database.close()

    def test_adaptation_telemetry_failure_cannot_fail_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            gateway = _gateway(
                resources, _Runtime("available response"),
                adaptation=_FailingAdaptation(),
            )

            accepted = gateway.ask(ShellAskCommand(
                "adaptation-telemetry-failure", "Keep the request available",
            ))
            with self.assertLogs(
                "fam_os.core.production.execution_worker", level="ERROR",
            ) as captured:
                result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.COMPLETED, result.result.status)
            self.assertEqual("available response", result.result.content)
            self.assertIn("adaptation telemetry failed", captured.output[0])
            resources.database.close()

    def test_concurrent_terminal_projection_returns_one_retained_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            outcomes = ProductVerifiedOutcomeLearning(resources.repositories)
            gateway = _gateway(
                resources, _Runtime("READY"), outcomes=outcomes,
                verifier=production_verifier(resources.repositories),
            )
            accepted = gateway.ask(ShellAskCommand(
                "learning-concurrent", "Reply with exactly READY",
                verification_required=True,
            ))
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = tuple(pool.map(
                    lambda _index: _terminal(gateway, accepted.session_id), range(8),
                ))
            self.assertTrue(all(item.result.content == "READY" for item in results))
            self.assertEqual(1, len(outcomes.records()))
            count = resources.database.execute(
                "SELECT count(*) FROM terminal_results WHERE request_id=?",
                ("learning-concurrent",),
            ).fetchone()[0]
            self.assertEqual(1, count)
            resources.database.close()

    def test_verified_terminal_outcome_learns_without_retaining_working_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            outcomes = ProductVerifiedOutcomeLearning(resources.repositories)
            gateway = _gateway(
                resources, _Runtime("READY"),
                verifier=production_verifier(resources.repositories),
                outcomes=outcomes,
            )
            prompt = "PHASE20_RAW_PROMPT_NONCE must never become a learning feature."
            specification = ExactTextVerification("READY")
            declaration = VerificationDeclaration(
                "declaration-learning-1", "learning-1",
                contract_for_kind(specification.kind), specification,
            )
            accepted = gateway.ask_verified(ShellVerifiedAskCommand(
                ShellAskCommand("learning-1", prompt, verification_required=True),
                dumps_document(declaration),
            ))
            result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertEqual("READY", result.result.content)
            self.assertEqual(TERMINAL_CONTENT_REDACTION, resources.requests.get(
                "learning-1",
            ).prompt)
            self.assertIsNone(
                resources.repositories.verifications.declaration_for_request("learning-1"),
            )
            records = outcomes.records()
            self.assertEqual(1, len(records))
            self.assertEqual("intent:conversation", records[0].workflow_id)
            self.assertFalse(records[0].prompt_retained)
            inference = resources.repositories.inference_executions.get(
                accepted.session_id,
            )
            candidate = resources.repositories.final_evidence.candidate(
                inference.candidate_id,
            )
            self.assertEqual(TERMINAL_CONTENT_REDACTION, candidate.content)
            repeated = gateway.snapshot(accepted.session_id)
            self.assertEqual("READY", repeated.result.content)
            resources.database.close()

    def test_unverified_terminal_outcome_is_retained_but_never_learned(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            outcomes = ProductVerifiedOutcomeLearning(resources.repositories)
            gateway = _gateway(
                resources, _Runtime("ordinary answer"), outcomes=outcomes,
            )
            accepted = gateway.ask(ShellAskCommand(
                "learning-2", "PHASE20_UNVERIFIED_PROMPT_NONCE",
            ))
            result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.COMPLETED, result.result.status)
            self.assertEqual((), outcomes.records())
            self.assertEqual(TERMINAL_CONTENT_REDACTION, resources.requests.get(
                "learning-2",
            ).prompt)
            self.assertEqual(
                "ordinary answer", gateway.snapshot(accepted.session_id).result.content,
            )
            resources.database.close()

    def test_adaptation_terminal_failure_cannot_undo_committed_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            outcomes = ProductVerifiedOutcomeLearning(
                resources.repositories, _FailingTerminalObserver(),
            )
            gateway = _gateway(
                resources, _Runtime("available result"), outcomes=outcomes,
            )

            accepted = gateway.ask(ShellAskCommand(
                "adaptation-terminal-failure", "Retain this terminal result",
            ))
            with self.assertLogs(
                "fam_os.product.verified_outcome_learning", level="ERROR",
            ) as captured:
                result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.COMPLETED, result.result.status)
            self.assertEqual("available result", result.result.content)
            retained = resources.repositories.terminal_outcomes.result(
                "adaptation-terminal-failure",
            )
            self.assertIsNotNone(retained)
            self.assertEqual(result.result.status, retained.status)
            self.assertEqual(result.result.content, retained.content)
            self.assertIn("terminal observation failed", captured.output[0])
            resources.database.close()

    def test_sanitized_terminal_result_and_learning_survive_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resources = _resources(root)
            outcomes = ProductVerifiedOutcomeLearning(resources.repositories)
            gateway = _gateway(
                resources, _Runtime("READY"), outcomes=outcomes,
                verifier=production_verifier(resources.repositories),
            )
            accepted = gateway.ask(ShellAskCommand(
                "learning-restart", "Reply with exactly READY",
                verification_required=True,
            ))
            self.assertEqual("READY", _terminal(gateway, accepted.session_id).result.content)
            self.assertEqual((), gateway._workers.active_ids())
            resources.database.close()

            reopened = _resources(root)
            restarted_outcomes = ProductVerifiedOutcomeLearning(reopened.repositories)
            restarted = _gateway(
                reopened, _Runtime(error=True), outcomes=restarted_outcomes,
            )
            result = restarted.snapshot(accepted.session_id)
            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertEqual("READY", result.result.content)
            self.assertEqual(1, len(restarted_outcomes.records()))
            self.assertEqual(
                TERMINAL_CONTENT_REDACTION,
                reopened.requests.get("learning-restart").prompt,
            )
            reopened.database.close()

    def test_grounded_identity_is_verified_and_released_with_exact_citation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            source_text = "FAM_OS is local operating-system intelligence above Linux."
            answer = source_text
            runtime = _Runtime(json.dumps({
                "answer": answer,
                "claims": [{
                    "text": answer,
                    "source_id": "identity-source",
                    "quote": answer,
                }],
            }))
            gateway = _gateway(
                resources, runtime, grounding=_Grounding(source_text),
                verifier=production_verifier(resources.repositories),
            )

            accepted = gateway.ask(ShellAskCommand(
                "grounded-1", "Explain what FAM_OS is",
            ))
            result = _terminal(gateway, accepted.session_id)

            self.assertEqual(
                ResultStatus.VERIFIED, result.result.status,
                f"{result.result.reason}; {result.message}",
            )
            self.assertEqual(answer, result.result.content)
            self.assertEqual(1, len(result.result.citations))
            self.assertEqual("package://identity", result.result.citations[0].source_locator)
            self.assertIn("text and quote must be byte-for-byte identical", runtime.prompts[0])
            self.assertIn(source_text, runtime.prompts[0])
            declaration = resources.repositories.verifications.declaration_for_request(
                "grounded-1",
            )
            self.assertIsNotNone(declaration)
            resources.database.close()

    def test_invalid_local_grounded_output_falls_back_to_declared_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            source_text = (
                "PHASE23_WORKSPACE_FACT: the resident fabric uses verified local evidence."
            )
            runtime = _Runtime('{"answer":"unrelated","claims":[]}')
            gateway = _gateway(
                resources, runtime, grounding=_Grounding(source_text),
                verifier=production_verifier(resources.repositories),
            )

            accepted = gateway.ask(ShellAskCommand(
                "grounded-extractive-fallback",
                "What exact PHASE23_WORKSPACE_FACT statement is in this workspace?",
            ))
            result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertEqual(source_text, result.result.content)
            self.assertEqual(1, len(result.result.citations))
            self.assertEqual(1, len(runtime.models))
            resources.database.close()

    def test_natural_request_survives_gateway_reconstruction_and_releases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            runtime = _Runtime("The durable answer.")
            gateway = _gateway(resources, runtime)
            accepted = gateway.ask(ShellAskCommand("request-1", "Explain FAM_OS"))

            restarted = _gateway(resources, runtime)
            result = _terminal(restarted, accepted.session_id)

            self.assertEqual(ShellRunState.TERMINAL, result.state)
            self.assertEqual(ResultStatus.COMPLETED, result.result.status)
            self.assertEqual("The durable answer.", result.result.content)
            self.assertIn("unverified", result.message)
            self.assertEqual("terminal", resources.requests.state("request-1"))
            resources.database.close()

    def test_verification_required_withholds_without_declared_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            gateway = _gateway(resources, _Runtime("plausible but unproved"))
            accepted = gateway.ask(ShellAskCommand(
                "request-2", "Prove this answer", verification_required=True,
            ))
            result = _terminal(gateway, accepted.session_id)
            self.assertEqual(ResultStatus.WITHHELD, result.result.status)
            self.assertIsNone(result.result.content)
            self.assertIn("verifier_unavailable", result.message)
            resources.database.close()

    def test_provider_failure_is_safe_and_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            gateway = _gateway(resources, _Runtime(error=True))
            accepted = gateway.ask(ShellAskCommand("request-3", "Say hello"))
            with self.assertLogs(
                "fam_os.core.production.execution_worker", level="ERROR",
            ) as captured:
                result = _terminal(gateway, accepted.session_id)
            self.assertEqual(ResultStatus.FAILED, result.result.status)
            self.assertNotIn("secret provider failure", result.result.reason)
            self.assertIn(
                "candidate generation failed for request request-3",
                "\n".join(captured.output),
            )
            self.assertIn("secret provider failure", "\n".join(captured.output))
            resources.database.close()

    def test_exact_verifier_escalates_with_feedback_and_releases_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            runtime = _Runtime(responses=("WRONG", "STILL_WRONG", "READY"))
            outcomes = ProductVerifiedOutcomeLearning(resources.repositories)
            gateway = _gateway(
                resources, runtime, strong=True, outcomes=outcomes,
                verifier=production_verifier(resources.repositories),
            )
            accepted = gateway.ask(ShellAskCommand(
                "request-4", "Reply with exactly READY", verification_required=True,
            ))
            result = _terminal(gateway, accepted.session_id)
            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertTrue(result.result.verified)
            self.assertEqual(
                ("qwen3:1.7b", "qwen3:1.7b", "strong:26b"),
                tuple(runtime.models),
            )
            self.assertIn("Expected exact bytes", runtime.prompts[-1])
            reservations = resources.database.execute(
                "SELECT kind,reserved_tokens FROM attempt_budget_reservations "
                "ORDER BY created_at"
            ).fetchall()
            self.assertEqual([("repair", 1024), ("escalation", 1024)], reservations)
            learned = outcomes.records()
            self.assertEqual(1, len(learned))
            self.assertTrue(learned[0].escalation_used)
            self.assertEqual("strong:26b", learned[0].expert_id)
            candidate_ids = tuple(
                row[0] for row in resources.database.fetchall(
                    "SELECT evidence_id FROM final_evidence "
                    "WHERE evidence_kind='candidate' AND request_id='request-4'",
                )
            )
            self.assertEqual(3, len(candidate_ids))
            self.assertTrue(all(
                resources.repositories.final_evidence.candidate(identifier).content
                == TERMINAL_CONTENT_REDACTION
                for identifier in candidate_ids
            ))
            runs = resources.repositories.verifications.runs_for_request("request-4")
            self.assertEqual(3, len(runs))
            self.assertTrue(all(
                run.feedback == TERMINAL_CONTENT_REDACTION for run in runs
            ))
            resources.database.close()

    def test_failed_verification_reaches_advisory_factory_observer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            observer = _FailureObserver()
            gateway = _gateway(
                resources, _Runtime(responses=("WRONG", "READY")),
                verifier=production_verifier(resources.repositories),
                failure_observer=observer,
            )
            accepted = gateway.ask(ShellAskCommand(
                "factory-observer", "Reply with exactly READY",
                verification_required=True,
            ))
            result = _terminal(gateway, accepted.session_id)

            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertEqual(1, len(observer.failures))
            record, decision = observer.failures[0]
            self.assertEqual("factory-observer", record.request_id)
            self.assertFalse(decision.passed)
            self.assertIsNotNone(decision.run_record)
            resources.database.close()

    def test_second_strong_model_is_independent_verified_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            runtime = _Runtime(responses=("WRONG", "WRONG", "WRONG", "READY"))
            gateway = _gateway(resources, runtime, fallback=True)
            accepted = gateway.ask(ShellAskCommand(
                "request-5", "Reply with exactly READY", verification_required=True,
            ))
            result = _terminal(gateway, accepted.session_id)
            self.assertEqual(ResultStatus.VERIFIED, result.result.status)
            self.assertEqual(
                ("qwen3:1.7b", "qwen3:1.7b", "laguna:strong", "gemma:26b"),
                tuple(runtime.models),
            )
            kinds = resources.database.execute(
                "SELECT kind FROM attempt_budget_reservations ORDER BY created_at"
            ).fetchall()
            self.assertEqual([("repair",), ("escalation",), ("escalation",)], kinds)
            resources.database.close()

    def test_ephemeral_memory_reaches_only_the_same_session_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            resources = _resources(Path(temporary))
            runtime = _Runtime(responses=("ORBIT", "ORBIT", "UNKNOWN"))
            memory = ProductionSessionMemory()
            gateway = _gateway(resources, runtime, memory=memory)

            first = gateway.ask(ShellAskCommand(
                "memory-1", "My codename is ORBIT.",
                memory_session_id="conversation-a",
            ))
            _terminal(gateway, first.session_id)
            second = gateway.ask(ShellAskCommand(
                "memory-2", "What is my codename?",
                memory_session_id="conversation-a",
            ))
            _terminal(gateway, second.session_id)
            isolated = gateway.ask(ShellAskCommand(
                "memory-3", "What is the other user's codename?",
                memory_session_id="conversation-b",
            ))
            _terminal(gateway, isolated.session_id)

            self.assertEqual("What is my codename?", runtime.prompts[1])
            self.assertIn("user: My codename is ORBIT.", runtime.messages[1][1])
            self.assertIn(
                "assistant assurance=unverified: ORBIT", runtime.messages[1][1],
            )
            self.assertNotIn("My codename is ORBIT.", runtime.prompts[2])
            self.assertEqual(
                "What is my codename?", resources.requests.get("memory-2").prompt,
            )
            resources.database.close()


class _Runtime:
    def __init__(self, content="", error=False, responses=()):
        self.content = content
        self.error = error
        self.responses = list(responses)
        self.models = []
        self.prompts = []
        self.messages = []
        self.contexts = []
        self.output_limits = []

    def chat(self, request):
        if self.error:
            raise RuntimeError("secret provider failure")
        self.models.append(request.model_ref)
        self.prompts.append(request.messages[-1].content)
        self.messages.append(tuple(message.content for message in request.messages))
        self.contexts.append(request.context_tokens)
        self.output_limits.append(request.max_output_tokens)
        content = self.responses.pop(0) if self.responses else self.content
        return InferenceResponse(
            content,
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 4, 400.0),
        )


class _Adaptation:
    def __init__(self):
        self.request_ids = []

    def preferred_model_refs(self, _intent):
        return ()

    def context_tokens(
        self, request_id, _intent, _model_ref, _messages,
        _max_output_tokens, _default_context_tokens,
    ):
        self.request_ids.append(request_id)
        return 4096

    def inference_completed(self, *_args):
        return None


class _FailingAdaptation(_Adaptation):
    def inference_completed(self, *_args):
        raise RuntimeError("adaptation telemetry unavailable")


class _FailingTerminalObserver:
    def terminal_committed(self, *_args):
        raise RuntimeError("adaptation terminal observer unavailable")


class _Grounding:
    def __init__(self, content):
        self.source = RetrievedSource(
            "identity-source", "package://identity", content,
            hashlib.sha256(content.encode("utf-8")).hexdigest(), "package-identity",
        )

    def declaration_for(self, request_id, prompt, _intent, _access):
        specification = RetrievalCitationsVerification(
            (self.source,), retrieval_query_obligation(prompt),
        )
        return VerificationDeclaration(
            f"declaration-{request_id}", request_id,
            contract_for_kind(specification.kind), specification,
        )


class _Resources:
    def __init__(self, database, composition, repositories):
        self.database = database
        self.composition = composition
        self.repositories = repositories
        self.requests = repositories.requests


class _FailureObserver:
    def __init__(self):
        self.failures = []

    def verification_failed(self, record, decision):
        self.failures.append((record, decision))


def _resources(root: Path) -> _Resources:
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    result = SecureStorage(
        database, OwnerKeyStore(root / "master.key", os.geteuid()),
    ).open()
    composition = CoreStorageComposition(database, result.cipher, str(os.geteuid()))
    return _Resources(database, composition, composition.repositories())


def _gateway(
    resources: _Resources, runtime, strong=False, fallback=False, memory=None,
    grounding=None, verifier=None, outcomes=None, adaptation=None,
    failure_observer=None,
) -> ProductionTaskGateway:
    verifier_ids = (
        "verifier.text.exact-v1", "python.deterministic-tests.v1",
        "retrieval.citations.v1", "math.sympy-equivalence.v1",
        "media.artifact-text.v1",
    )
    entries = [RuntimeModelEntry(
        "qwen3:1.7b", "economical", tuple(ModelIntent), 1024**3, 8192, "0" * 64,
        verifier_ids,
    )]
    if strong:
        entries.append(RuntimeModelEntry(
            "strong:26b", "escalation", tuple(ModelIntent), 8 * 1024**3,
            8192, "1" * 64, verifier_ids,
        ))
    if fallback:
        entries.extend((
            RuntimeModelEntry(
                "laguna:strong", "escalation", tuple(ModelIntent), 9 * 1024**3,
                8192, "2" * 64, verifier_ids,
            ),
            RuntimeModelEntry(
                "gemma:26b", "escalation", tuple(ModelIntent), 8 * 1024**3,
                8192, "3" * 64, verifier_ids,
            ),
        ))
    selector = ResourceAwareModelSelector(
        RuntimeModelCatalog(tuple(entries)), adaptation,
    )
    return ProductionTaskGateway(
        runtime, resources.repositories, selector,
        lambda: HostCapacity(16 * 1024**3), resources.composition.budget_ledger,
        memory=memory, grounding=grounding, verifier=verifier, outcomes=outcomes,
        adaptation=adaptation, failure_observer=failure_observer,
    )


def _terminal(gateway, session_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = gateway.snapshot(session_id)
        if snapshot.state is ShellRunState.TERMINAL:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("task did not become terminal")


if __name__ == "__main__":
    unittest.main()
