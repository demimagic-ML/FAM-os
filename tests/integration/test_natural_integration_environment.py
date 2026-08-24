import hashlib
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.integration import NaturalIntegrationEnvironmentPlanner
from fam_os.adapters.filesystem import (
    BoundedCandidateContextReader,
    BoundedFilesystemRepositoryObserver,
)
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore,
    SQLiteCandidateEditStore,
    SQLiteCandidateGenerationStore,
    SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore,
    SQLiteLocalGitDeliveryStore,
    SQLiteNaturalEngineeringProposalStore,
)
from fam_os.core.engineering import (
    CandidateGenerationService,
    CandidateVerificationService,
    EngineeringAuthorizationDecision,
    EngineeringEcosystem,
    EngineeringToolReceipt,
    IntegrationAllocatedPort,
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStartResult,
    IntegrationEnvironmentStatus,
    IntegrationExecutionPermit,
    IntegrationServiceReceipt,
    LocalGitDeliveryService,
    NaturalIntegrationEnvironmentDeclaration,
    NaturalIntegrationServiceDeclaration,
    NaturalIntegrationServiceTemplate,
    ToolQualificationStatus,
    ToolRecipePurpose,
    integration_environment_plan_digest,
)
from fam_os.schemas import dumps_document, loads_document
from fam_os.core.ports.inference import InferenceResponse
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.product.natural_engineering_integration import (
    NaturalEngineeringIntegrationCoordinator,
)
from fam_os.product.storage.integration_environment_repository import (
    StoredIntegrationEnvironment,
)
from fam_os.telemetry.contracts import InferenceMetrics


class NaturalIntegrationEnvironmentLifecycleTests(unittest.TestCase):
    def test_natural_preview_is_bound_before_apply_and_repeated_after_apply(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "project"
            workspace.mkdir()
            (workspace / "index.html").write_text("<h1>Before</h1>\n")
            (workspace / "api.py").write_text("# fixed root API entry point\n")
            subprocess.run(("git", "init", "-q", str(workspace)), check=True)
            subprocess.run(
                ("git", "-C", str(workspace), "add", "index.html", "api.py"),
                check=True,
            )
            subprocess.run((
                "git", "-C", str(workspace), "-c", "user.name=Test",
                "-c", "user.email=test@example.invalid", "commit", "-q",
                "-m", "initial",
            ), check=True)
            authority = _Authority()
            recipes = _Recipes()
            verification_store = SQLiteCandidateVerificationStore(
                root / "verifications.sqlite3",
            )
            loop = ProductEngineeringLoopApi(
                "owner-1", authority,
                SQLiteEngineeringLoopStore(root / "loop.sqlite3"),
                root / "candidates",
                SQLiteEngineeringPreparationStore(root / "preparation.sqlite3"),
                authority, SQLiteCandidateEditStore(root / "edits.sqlite3"),
                CandidateVerificationService(
                    authority, recipes, _Runner(), _Verifier(),
                    verification_store,
                ),
                verification_store,
                SQLiteCandidateChangesetStore(root / "changesets.sqlite3"),
                recipes,
                LocalGitDeliveryService(
                    authority, LocalGitAdapter(),
                    SQLiteLocalGitDeliveryStore(root / "git.sqlite3"),
                ),
            )
            environments = _Environments()
            integration = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-test"),
                port_allocator=iter((43141, 43142, 43143, 43144)).__next__,
            )
            executor = NaturalEngineeringExecutionCoordinator(
                loop, BoundedCandidateContextReader(),
                CandidateGenerationService(
                    _Runtime(), "model:1",
                    SQLiteCandidateGenerationStore(root / "generation.sqlite3"),
                ),
                integration=integration,
            )
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(root / "proposals.sqlite3"),
                _Authentication(), authority, loop,
                BoundedFilesystemRepositoryObserver(), executor=executor,
                identifier=lambda: "integration-lifecycle",
            )

            proposal = api.propose(
                "owner-1",
                (
                    "Update index.html and run the full-stack API and site "
                    "end-to-end before applying."
                ),
                str(workspace),
            )
            prepared = api.activate(
                "owner-1", proposal["proposal_id"], "session-1",
                confirmed=True,
            )["engineering_task"]

            self.assertEqual("changeset_approval_required", prepared["outcome"])
            self.assertEqual("<h1>Before</h1>\n", (workspace / "index.html").read_text())
            self.assertEqual(1, len(prepared["integration_environment_receipt_ids"]))
            evidence = prepared["changeset"]["payload"]["preview"][
                "verification_evidence_ids"
            ]
            self.assertIn(prepared["integration_environment_receipt_ids"][0], evidence)

            completed = api.approve_changeset(
                "owner-1", proposal["proposal_id"],
                prepared["changeset"]["payload"]["changeset_id"],
                "session-1", confirmed=True,
            )["engineering_task"]

            self.assertEqual("local_commit_completed", completed["outcome"])
            self.assertEqual("<h1>After</h1>\n", (workspace / "index.html").read_text())
            self.assertIsInstance(
                loads_document((workspace / "fam.integration.json").read_text()),
                NaturalIntegrationEnvironmentDeclaration,
            )
            self.assertEqual(
                1, len(completed["integration_environment_postapply_receipt_ids"]),
            )
            self.assertEqual(2, environments.start_count)
            self.assertTrue(all(item.state == "cleaned" for item in environments.values.values()))
            self.assertTrue(all(
                len(item.start_result.receipt.services) == 2
                for item in environments.values.values()
            ))
            self.assertEqual(
                {
                    ("backend-candidate", "frontend-candidate"),
                    ("backend-postapply", "frontend-postapply"),
                },
                {
                    tuple(service.service_id for service in item.plan.services)
                    for item in environments.values.values()
                },
            )
            progress = api.progress("owner-1", proposal["proposal_id"])
            self.assertEqual(
                2, len(progress["engineering_task"]["integration_environments"]),
            )
            api.close()
            loop.close()


class _Authentication:
    def issue(self, owner_id, purpose, digest, transport_session_id=None):
        return type("Context", (), {
            "context_id": f"context:{transport_session_id}",
        })()

    def belongs_to_session(self, context_id, session_id):
        return context_id == f"context:{session_id}"


class _Authority:
    def __init__(self):
        self.grant = None
        self.index = 0

    def activate(self, grant, approval):
        self.grant = grant

    def usable(self, grant_id):
        return self.grant if self.grant and self.grant.grant_id == grant_id else None

    def authorize(self, request):
        self.index += 1
        allowed = self.usable(request.grant_id) is not None
        return EngineeringAuthorizationDecision(
            f"decision-{self.index}", request.request_id, request.grant_id,
            request.authority, datetime.now(timezone.utc), allowed,
            "authorized" if allowed else "grant_unavailable",
        )


class _Recipes:
    recipes = tuple(
        type("Recipe", (), {
            "recipe_id": f"engineering.{ecosystem.value}.test",
            "recipe_version": "1.0.0",
            "ecosystem": ecosystem,
            "executable_path": "/usr/bin/python3",
            "purpose": ToolRecipePurpose.TEST,
        })()
        for ecosystem in (EngineeringEcosystem.HTML, EngineeringEcosystem.PYTHON)
    )

    def get(self, recipe_id, version):
        for recipe in self.recipes:
            if (recipe_id, version) == (recipe.recipe_id, recipe.recipe_version):
                return recipe
        raise LookupError("recipe unavailable")

    def matching(self, toolchain, purposes):
        return tuple(
            recipe for recipe in self.recipes
            if toolchain in {
                recipe.ecosystem.value,
                recipe.executable_path.rsplit("/", 1)[-1],
            }
        )


class _Runtime:
    def chat(self, request):
        return InferenceResponse(
            json.dumps({
                "contract_version": "fam.core.engineering/v1alpha1",
                "summary": "Update the heading",
                "operations": [
                    {
                        "kind": "replace_file", "path": "index.html",
                        "content": "<h1>After</h1>\n", "source_path": None,
                        "media_type": "text/html",
                    },
                    {
                        "kind": "create_file", "path": "fam.integration.json",
                        "content": _DECLARATION, "source_path": None,
                        "media_type": "application/json",
                    },
                ],
            }),
            InferenceMetrics("model:1", 0.1, 0.0, 20, 20),
        )


class _Runner:
    def run(self, task_id, candidate, recipe_id, recipe_version, profile):
        now = datetime.now(timezone.utc)
        suffix = hashlib.sha256(
            f"{candidate.candidate_id}:{recipe_id}".encode()
        ).hexdigest()[:8]
        return EngineeringToolReceipt(
            f"tool-{suffix}", task_id, candidate.candidate_id, recipe_id,
            "a" * 64, profile.profile_id, "b" * 64, now, now, 0,
            "c" * 64, "d" * 64, (), (),
            ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"),
            ToolQualificationStatus.PASSED,
        )


class _Verifier:
    def verify(self, receipt, recipe_version):
        return type("Result", (), {
            "passed": True, "verifier_ids": ("verifier-html",),
            "reason": "passed",
        })()


class _Environments:
    def __init__(self):
        self.values = {}
        self.start_count = 0

    def inspect(self, owner_id, environment_id):
        if environment_id not in self.values:
            raise KeyError(environment_id)
        return self.values[environment_id]

    def for_task(self, owner_id, task_id):
        return tuple(
            item for item in self.values.values() if item.plan.task_id == task_id
        )

    def start(self, owner_id, plan, candidate, *arguments):
        self.start_count += 1
        permit = IntegrationExecutionPermit(
            f"permit-{plan.environment_id}", plan.environment_id,
            plan.approved_changeset_id, plan.exact_host_id, ("decision-env",),
            plan.created_at, plan.created_at + timedelta(minutes=5),
        )
        service_receipts = tuple(
            IntegrationServiceReceipt(
                service.service_id,
                f"runtime-{plan.environment_id}-{service.service_id}", None,
                tuple(IntegrationAllocatedPort(
                    port.name, port.requested_host_port,
                ) for port in service.ports),
                f"health-{plan.environment_id}-{service.service_id}", None,
            )
            for service in plan.services
        )
        ready = IntegrationEnvironmentReceipt(
            f"ready-{plan.environment_id}", plan.environment_id,
            permit.permit_id, IntegrationEnvironmentStatus.READY,
            plan.created_at, plan.created_at + timedelta(seconds=1),
            service_receipts, (), (),
        )
        result = IntegrationEnvironmentStartResult(
            plan.environment_id, integration_environment_plan_digest(plan),
            permit, ready,
        )
        self.values[plan.environment_id] = StoredIntegrationEnvironment(
            plan, candidate, result, ready, "active",
        )
        return result

    def cleanup(self, owner_id, environment_id):
        stored = self.values[environment_id]
        cleaned = replace(
            stored.latest_receipt,
            receipt_id=f"cleaned-{environment_id}",
            status=IntegrationEnvironmentStatus.CLEANED,
            completed_at=stored.latest_receipt.completed_at + timedelta(seconds=1),
            cleanup_evidence_ids=(f"stopped-{environment_id}",),
        )
        self.values[environment_id] = replace(
            stored, latest_receipt=cleaned, state="cleaned",
        )
        return cleaned


_DECLARATION = dumps_document(NaturalIntegrationEnvironmentDeclaration(
    "generated-full-stack",
    (
        NaturalIntegrationServiceDeclaration(
            "backend", NaturalIntegrationServiceTemplate.PYTHON_API, (),
        ),
        NaturalIntegrationServiceDeclaration(
            "frontend", NaturalIntegrationServiceTemplate.STATIC_SITE,
            ("backend",),
        ),
    ),
))


if __name__ == "__main__":
    unittest.main()
