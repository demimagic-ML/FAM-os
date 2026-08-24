import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier, sign_recipe_specification,
)
from fam_os.adapters.sqlite import SQLiteRuntimeDiagnosticStore
from fam_os.core.engineering import (
    CandidateBaselineEntry, CandidateEntryKind, CandidateWorkspace,
    EngineeringAuthorizationDecision, EngineeringEcosystem,
    EngineeringSandboxProfile,
    NaturalLanguageEngineeringPlanner, RuntimeDiagnosticIntentPolicy,
    RuntimeDiagnosticPhase, RuntimeDiagnosticReceipt,
    RuntimeDiagnosticRecipePolicy, RuntimeDiagnosticService,
    RuntimeDiagnosticStatus,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import (
    ToolRecipeSpecification, diagnostic_recipe_specifications,
)


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


class RuntimeDiagnosticCompositionTests(unittest.TestCase):
    def test_natural_intent_selects_signed_recipes_and_exact_candidate_target(self):
        catalog = _catalog()
        proposal = _proposal(
            "Profile CPU and inspect memory usage of bench.py.",
        )
        candidate, entries = _candidate(proposal.definition.task.task_id)
        requests = RuntimeDiagnosticIntentPolicy(catalog).plan(
            proposal.definition, candidate, entries, ("bench.py",),
            phase=RuntimeDiagnosticPhase.CANDIDATE,
            session_id="session-1", principal_id="owner-1", now=NOW,
        )

        self.assertEqual(("cpu_profile", "memory_profile"), tuple(
            item.kind.value for item in requests
        ))
        self.assertTrue(all(item.target_argv == ("bench.py",) for item in requests))
        self.assertTrue(all(item.grant_id == proposal.grant.grant_id for item in requests))
        for request in requests:
            self.assertEqual(
                request.signed_recipe_id,
                RuntimeDiagnosticRecipePolicy(catalog).admit(request).recipe_id,
            )

    def test_distributed_trace_is_not_misrepresented_as_local_strace(self):
        policy = RuntimeDiagnosticIntentPolicy(_catalog())
        with self.assertRaisesRegex(LookupError, "service environment"):
            policy.requested_kinds("Collect a distributed trace across the API")

    def test_plain_profile_and_debug_words_select_safe_default_disciplines(self):
        policy = RuntimeDiagnosticIntentPolicy(_catalog())
        self.assertEqual(
            ("cpu_profile",),
            tuple(item.value for item in policy.requested_kinds("Profile bench.py")),
        )
        self.assertEqual(
            ("stack_trace",),
            tuple(item.value for item in policy.requested_kinds("Debug app.py")),
        )

    def test_natural_selection_rejects_ambiguous_signed_recipe_versions(self):
        key = Ed25519PrivateKey.from_private_bytes(b"\x08" * 32)
        catalog = _catalog()
        original = diagnostic_recipe_specifications()[0]
        catalog.admit(sign_recipe_specification(
            ToolRecipeSpecification(
                EngineeringEcosystem.PYTHON, original.purpose,
                original.executable_path, original.argv,
                original.verifier_id,
            ),
            "release-key", key,
        ))
        proposal = _proposal("Debug bench.py.")
        candidate, entries = _candidate(proposal.definition.task.task_id)

        with self.assertRaisesRegex(LookupError, "ambiguous"):
            RuntimeDiagnosticIntentPolicy(catalog).plan(
                proposal.definition, candidate, entries, ("bench.py",),
                phase=RuntimeDiagnosticPhase.CANDIDATE,
                session_id="session-1", principal_id="owner-1", now=NOW,
            )

    def test_core_service_authorizes_twice_persists_and_reconciles_retry(self):
        catalog = _catalog()
        proposal = _proposal("Profile CPU usage of bench.py.")
        candidate, entries = _candidate(proposal.definition.task.task_id)
        preparation = SimpleNamespace(
            definition_id=proposal.definition.definition_id,
            candidate=candidate,
        )
        request = RuntimeDiagnosticIntentPolicy(catalog).plan(
            proposal.definition, candidate, entries, ("bench.py",),
            phase=RuntimeDiagnosticPhase.CANDIDATE,
            session_id="session-1", principal_id="owner-1", now=NOW,
        )[0]
        limits = request.limits
        profile = EngineeringSandboxProfile(
            "runtime-profile-1", limits.memory_bytes, limits.cpu_seconds,
            limits.wall_seconds, limits.process_limit, limits.output_bytes,
            limits.temporary_file_bytes, request.network_mode, (), (),
        )
        authority = _Authority()
        runner = _Runner()
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteRuntimeDiagnosticStore(
                Path(temporary) / "diagnostics.sqlite3",
            )
            service = RuntimeDiagnosticService(
                authority, RuntimeDiagnosticRecipePolicy(catalog), runner, store,
                clock=lambda: NOW, identifier=lambda: "fixed",
            )
            first = service.execute(
                proposal.definition, preparation, request, profile,
            )
            second = service.execute(
                proposal.definition, preparation, request, profile,
            )

            self.assertEqual(first, second)
            self.assertEqual(1, runner.calls)
            self.assertEqual(2, authority.calls)
            self.assertEqual((request,), store.requests_for_task(request.task_id))
            self.assertEqual((first,), store.receipts_for_task(request.task_id))
            self.assertEqual(("decision-2",), first.authorization_decision_ids)
            store.close()


class _Authority:
    def __init__(self):
        self.calls = 0

    def authorize(self, request):
        self.calls += 1
        return EngineeringAuthorizationDecision(
            f"decision-{self.calls}", request.request_id, request.grant_id,
            request.authority, NOW, True, "authorized",
        )


class _Runner:
    def __init__(self):
        self.calls = 0

    def run(self, request, candidate, profile, *, authorization_decision_ids):
        self.calls += 1
        empty = hashlib.sha256(b"").hexdigest()
        return RuntimeDiagnosticReceipt(
            "receipt-1", request.request_id, request.task_id,
            request.candidate_id, request.signed_recipe_id,
            request.signed_recipe_version, request.recipe_payload_sha256,
            profile.profile_id, NOW, NOW, RuntimeDiagnosticStatus.PASSED, 0,
            empty, empty, (), (), ("sandbox",),
            authorization_decision_ids,
        )


def _catalog():
    key = Ed25519PrivateKey.from_private_bytes(b"\x08" * 32)
    catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
        "release-key": key.public_key(),
    }))
    for specification in diagnostic_recipe_specifications():
        catalog.admit(sign_recipe_specification(
            specification, "release-key", key,
        ))
    return catalog


def _proposal(intent):
    return NaturalLanguageEngineeringPlanner().propose(
        prompt=intent, workspace_root="/workspace", owner_id="owner-1",
        principal_id="owner-1", task_id="task-1", grant_id="grant-1",
        toolchains=("python3",), now=NOW,
    )


def _candidate(task_id):
    entry = CandidateBaselineEntry(
        "bench.py", CandidateEntryKind.FILE, "a" * 64, 10, False,
    )
    candidate = CandidateWorkspace(
        "candidate-1", task_id, "baseline-1", "/workspace",
        "/candidate", NOW, "copy", "b" * 64, (entry,),
    )
    return candidate, (entry,)


if __name__ == "__main__":
    unittest.main()
