import json
import hashlib
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.sqlite import SQLiteCandidateGenerationStore
from fam_os.core.engineering import (
    CandidateBaselineEntry, CandidateContextDocument,
    CandidateEntryKind, CandidateGenerationContext,
    CandidateGenerationService, CandidateGenerationStatus,
    CandidateWorkspace, CheckpointPolicy, EngineeringAuthority,
    EngineeringOperation, EngineeringPreparationResult,
    EngineeringResourceImpact, EngineeringTaskDefinition,
    EngineeringTaskEnvelope, engineering_task_digest,
)
from fam_os.core.engineering.repository import (
    ArchitectureArea, ArchitectureDecision, ArchitectureProposal,
    RepositoryAnalysis,
)
from fam_os.core.engineering.candidate_generation_record import (
    CandidateGenerationRecord,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey
from fam_os.product.storage.owner_contract_codec import OwnerBoundContractCodec
from fam_os.telemetry.contracts import InferenceMetrics


NOW = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)


class CandidateGenerationServiceTests(unittest.TestCase):
    def test_natural_integration_prompt_exposes_only_declarative_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Keep app unchanged in this prompt test",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))
            definition, preparation, context = _inputs()
            integration_task = replace(
                definition.task,
                intent="Update the API and run the full-stack app end-to-end",
            )
            definition = EngineeringTaskDefinition(
                definition.definition_id, integration_task,
                definition.acceptance_policy_id, definition.created_at,
                engineering_task_digest(integration_task),
            )
            service = CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            )
            service.generate(
                definition, preparation, context, generation_id="generation-hint",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
            )
            prompt = runtime.requests[0].messages[1].content
            self.assertIn("optional_natural_integration_declaration", prompt)
            self.assertIn("fam.integration.json", prompt)
            self.assertIn("python_api", prompt)
            self.assertNotIn("integration.python.root-api", prompt)
            store.close()

    def test_invalid_output_repairs_and_validated_plan_survives_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generation.sqlite3"
            runtime = _Runtime(("not json", json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Fix app",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            })))
            store = SQLiteCandidateGenerationStore(path)
            service = CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            )
            record = service.generate(
                *_inputs(), generation_id="generation-1", session_id="session-1",
                principal_id="owner-1", available_tokens=20_000,
                available_wall_seconds=300,
            )
            self.assertEqual(CandidateGenerationStatus.PLAN_VALIDATED, record.status)
            self.assertEqual(2, record.attempt_count)
            self.assertEqual(18, record.consumed_tokens)
            self.assertIn(
                "Expecting value", runtime.requests[1].messages[-1].content,
            )
            store.close()

            reopened = SQLiteCandidateGenerationStore(path)
            replay = CandidateGenerationService(
                _Runtime(()), "model:1", reopened, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-1", session_id="session-1",
                principal_id="owner-1", available_tokens=20_000,
                available_wall_seconds=300,
            )
            self.assertEqual(record, replay)
            reopened.close()

    def test_prompt_evidence_is_fitted_without_evicting_the_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            definition, preparation, context = _inputs()
            paths = tuple(f"src/module-{index:03d}.py" for index in range(40))
            documents = tuple(
                CandidateContextDocument(
                    path,
                    hashlib.sha256(("VALUE = '" + "x" * 900 + "'\n").encode()).hexdigest(),
                    "VALUE = '" + "x" * 900 + "'\n",
                )
                for path in paths
            )
            context = CandidateGenerationContext(
                context.candidate_id, context.baseline_tree_sha256,
                tuple(sorted((*context.inventory_paths, *paths))),
                documents, False,
            )
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Fix app",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))

            record = CandidateGenerationService(
                runtime, "model:1", store, maximum_prompt_bytes=4_096,
                clock=lambda: NOW,
            ).generate(
                definition, preparation, context,
                generation_id="generation-bounded-prompt",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
            )

            self.assertEqual(CandidateGenerationStatus.PLAN_VALIDATED, record.status)
            user_prompt = runtime.requests[0].messages[1].content
            data = json.loads(user_prompt.split(": ", 1)[1])
            self.assertTrue(data["context_truncated"])
            self.assertLessEqual(
                len(json.dumps(
                    data, sort_keys=True, separators=(",", ":"),
                ).encode()),
                4_096,
            )
            self.assertLessEqual(runtime.requests[0].max_output_tokens, 8_192)
            store.close()

    def test_exhausted_invalid_output_is_terminal_without_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            record = CandidateGenerationService(
                _Runtime(("bad", "still bad")), "model:1", store,
                clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-2", session_id="session-1",
                principal_id="owner-1", available_tokens=20_000,
                available_wall_seconds=300,
            )
            self.assertEqual(CandidateGenerationStatus.FAILED, record.status)
            self.assertIsNone(record.plan)
            self.assertEqual("model_output_invalid", record.failure_code)
            store.close()

    def test_repair_prompt_marks_current_candidate_and_operation_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Repair app",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))
            CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-repair-prompt",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
                repair_feedback=("ReferenceError: require is not defined",),
            )
            data = json.loads(
                runtime.requests[0].messages[1].content.split(": ", 1)[1]
            )
            self.assertTrue(data["repair_mode"])
            self.assertIn("ReferenceError", data["untrusted_verifier_feedback"][0])
            self.assertIn(
                "replace_file only for existing inventory paths",
                runtime.requests[0].messages[0].content,
            )
            store.close()

    def test_state_conflicting_plan_is_repaired_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            runtime = _Runtime((
                json.dumps({
                    "contract_version": ENGINEERING_CONTRACT_VERSION,
                    "summary": "Wrong operation kind",
                    "operations": [{
                        "kind": "create_file", "path": "app.py",
                        "content": "VALUE = 2\n", "source_path": None,
                        "media_type": "text/x-python",
                    }],
                }),
                json.dumps({
                    "contract_version": ENGINEERING_CONTRACT_VERSION,
                    "summary": "Corrected operation kind",
                    "operations": [{
                        "kind": "replace_file", "path": "app.py",
                        "content": "VALUE = 2\n", "source_path": None,
                        "media_type": "text/x-python",
                    }],
                }),
            ))

            record = CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-semantic-repair",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
            )

            self.assertEqual(CandidateGenerationStatus.PLAN_VALIDATED, record.status)
            self.assertEqual(2, record.attempt_count)
            self.assertEqual("replace_file", record.plan.operations[0].kind.value)
            self.assertIn("trusted candidate state", runtime.requests[1].messages[-1].content)
            store.close()

    def test_repair_canonicalizes_reemitted_existing_file_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteCandidateGenerationStore(Path(temporary) / "g.sqlite3")
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Repair existing app",
                "operations": [{
                    "kind": "create_file", "path": "app.py",
                    "content": "VALUE = 2\n", "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))
            record = CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-repair-normalized",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
                repair_feedback=("fixture verification failed",),
            )
            self.assertEqual(CandidateGenerationStatus.PLAN_VALIDATED, record.status)
            self.assertEqual(1, record.attempt_count)
            self.assertEqual("replace_file", record.plan.operations[0].kind.value)
            store.close()

    def test_owner_bound_secure_store_hides_generated_source_and_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "secure-generation.sqlite3"
            codec = _owner_codec("owner-1")
            content = "TOP_SECRET_GENERATED_CONTENT = 2\n"
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Fix app",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": content, "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))
            store = SQLiteCandidateGenerationStore(path, codec)
            record = CandidateGenerationService(
                runtime, "model:1", store, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-secure",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
            )
            self.assertEqual(CandidateGenerationStatus.PLAN_VALIDATED, record.status)
            store.close()

            self.assertNotIn(content.encode("utf-8"), path.read_bytes())
            reopened = SQLiteCandidateGenerationStore(path, _owner_codec("owner-1"))
            self.assertEqual(record, reopened.load("generation-secure"))
            reopened.close()

            wrong_owner = SQLiteCandidateGenerationStore(path, _owner_codec("owner-2"))
            with self.assertRaises(Exception):
                wrong_owner.load("generation-secure")
            wrong_owner.close()

    def test_secure_store_migrates_existing_plaintext_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generation.sqlite3"
            content = "PRIVATE_LEGACY_GENERATED_CONTENT = 3\n"
            runtime = _Runtime((json.dumps({
                "contract_version": ENGINEERING_CONTRACT_VERSION,
                "summary": "Migrate generated plan",
                "operations": [{
                    "kind": "replace_file", "path": "app.py",
                    "content": content, "source_path": None,
                    "media_type": "text/x-python",
                }],
            }),))
            legacy = SQLiteCandidateGenerationStore(path)
            record = CandidateGenerationService(
                runtime, "model:1", legacy, clock=lambda: NOW,
            ).generate(
                *_inputs(), generation_id="generation-legacy",
                session_id="session-1", principal_id="owner-1",
                available_tokens=20_000, available_wall_seconds=300,
            )
            legacy.close()
            marker = b"PRIVATE_LEGACY_GENERATED_CONTENT"
            self.assertIn(marker, path.read_bytes())

            secure = SQLiteCandidateGenerationStore(path, _owner_codec("owner-1"))
            self.assertEqual(record, secure.load("generation-legacy"))
            secure.close()
            self.assertNotIn(marker, path.read_bytes())


class _Runtime:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        content = self.outputs.pop(0)
        return InferenceResponse(
            content, InferenceMetrics("model:1", 0.2, 0, 5, 4),
        )


def _inputs():
    task = EngineeringTaskEnvelope(
        "task-1", "owner-1", "grant-1", "Fix app", NOW,
        NOW + timedelta(hours=1), ("/workspace/project",),
        (
            EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
            EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE,
        ),
        (
            EngineeringOperation.READ, EngineeringOperation.REPLACE,
            EngineeringOperation.RUN_TOOL,
        ),
        (), (".git/**", ".fam/**"), ("python3",), (), (), 300, 8, 8,
        10_000, None, None, CheckpointPolicy.EVERY_CHANGESET,
    )
    definition = EngineeringTaskDefinition(
        "definition-task-1", task, "acceptance", NOW,
        engineering_task_digest(task),
    )
    candidate = CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", "/workspace/project",
        "/tmp/candidate-1/workspace", NOW, "copy", "b" * 64,
        (CandidateBaselineEntry(
            "app.py", CandidateEntryKind.FILE, "a" * 64, 10, False,
        ),),
    )
    evidence = SimpleNamespace(
        bundle_id="bundle-1", task_id="task-1",
    )
    analysis = RepositoryAnalysis(
        "analysis-1", "request-1", "task-1", "bundle-1", NOW,
        ("app.py",), (), (), (), (), (), "e" * 64, False,
    )
    decisions = tuple(
        ArchitectureDecision(area, False, "Keep boundary", ("app.py",))
        for area in ArchitectureArea
    )
    proposal = ArchitectureProposal(
        "proposal-1", "task-1", "analysis-1", NOW, "Fix app",
        decisions, (), True,
    )
    preparation = EngineeringPreparationResult(
        "definition-task-1", evidence, analysis, proposal, candidate,
    )
    content = "VALUE = 1\n"
    document = CandidateContextDocument(
        "app.py", hashlib.sha256(content.encode()).hexdigest(), content,
    )
    context = CandidateGenerationContext(
        "candidate-1", "b" * 64, ("app.py",), (document,), False,
    )
    return definition, preparation, context


def _owner_codec(owner_id: str) -> OwnerBoundContractCodec:
    key = bytes(range(32))
    key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
    return OwnerBoundContractCodec(
        ProductPayloadCipher(OwnerMasterKey(key_id, key)), owner_id,
        "engineering-candidate-generation", CandidateGenerationRecord,
    )


if __name__ == "__main__":
    unittest.main()
