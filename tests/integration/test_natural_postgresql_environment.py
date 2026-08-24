"""Real natural PostgreSQL template through Core and the Docker adapter."""

import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.integration import (
    DockerCommandClient,
    DockerIntegrationEnvironmentAdapter,
    NaturalIntegrationEnvironmentPlanner,
)
from fam_os.adapters.database import (
    NaturalPostgreSQLVerificationPlanBuilder,
    PostgreSQLIntegrationVerificationAdapter,
)
from fam_os.adapters.integration.postgresql_template import (
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
)
from fam_os.core.engineering import (
    CandidateWorkspace,
    CandidateBaselineEntry,
    CandidateEntryKind,
    EngineeringAuthorizationDecision,
    EngineeringAuthority,
    IntegrationEnvironmentService,
    NaturalLanguageEngineeringPlanner,
    PostgreSQLIntegrationVerificationService,
)
from fam_os.product.composition.integration_environment import (
    ProductDockerHealthRecipes,
)
from fam_os.product.natural_engineering_integration import (
    NaturalEngineeringIntegrationCoordinator,
)


class NaturalPostgreSQLIntegrationTests(unittest.TestCase):
    def test_natural_coordinator_wires_migration_before_guaranteed_cleanup(self):
        client = DockerCommandClient(maximum_output_bytes=64 * 1024 * 1024)
        observed = client.run((
            "image", "inspect", "--format", "{{.Id}}", POSTGRESQL_IMAGE_REF,
        ))
        if observed.exit_code != 0:
            self.skipTest("cached PostgreSQL image is unavailable")
        now = datetime.now(timezone.utc)
        prompt = (
            "Create a PostgreSQL migration and run a PostgreSQL service "
            "end-to-end using PostgreSQL secret ref secret.postgres-natural."
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owner, candidate_root = root / "owner", root / "candidate"
            owner.mkdir()
            (candidate_root / "db").mkdir(parents=True)
            files = {
                "db/001.up.sql": (
                    "CREATE TABLE messages(id bigint primary key, body text);\n"
                    "INSERT INTO messages VALUES (1, 'wired');\n"
                ),
                "db/001.down.sql": "DROP TABLE messages;\n",
            }
            for relative, content in files.items():
                (candidate_root / relative).write_text(content, encoding="utf-8")
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=prompt, workspace_root=str(owner), owner_id="owner-1",
                principal_id="owner-1", task_id="task-postgresql-wired",
                grant_id="grant-postgresql-wired", toolchains=("sql",), now=now,
            )
            entries = tuple(
                CandidateBaselineEntry(
                    relative, CandidateEntryKind.FILE,
                    hashlib.sha256(content.encode()).hexdigest(),
                    len(content.encode()), False,
                )
                for relative, content in sorted(files.items())
            )
            candidate = CandidateWorkspace(
                "candidate-postgresql-wired", "task-postgresql-wired",
                "baseline-1", str(owner), str(candidate_root), now, "copy",
                "a" * 64, entries,
            )
            resource = proposal.integration_resource_grant
            authority = _Authority(proposal.grant, resource)
            adapter = DockerIntegrationEnvironmentAdapter(
                _PostgreSQLSecrets(), client,
                health_recipes=ProductDockerHealthRecipes(client),
            )
            environments = _DirectEnvironments(
                IntegrationEnvironmentService(authority, adapter),
            )
            loop = _CoordinatorLoop(candidate)
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop,
                environments,
                NaturalIntegrationEnvironmentPlanner("host-real-wired"),
                clock=lambda: now,
                port_allocator=lambda: 43199,
                resource_grant_resolver=lambda identity: (
                    resource if identity == resource.grant_id else None
                ),
                postgresql_planner=NaturalPostgreSQLVerificationPlanBuilder(),
                postgresql_verifier=PostgreSQLIntegrationVerificationService(
                    authority,
                    PostgreSQLIntegrationVerificationAdapter(
                        _Protector(), client,
                    ),
                ),
            )

            result = coordinator.run_candidate(
                "owner-1", proposal.definition, candidate, tuple(files),
                "changeset-postgresql-wired", session_id="session-1",
                principal_id="owner-1",
            )

            self.assertTrue(result.postgresql_verification.passed)
            self.assertEqual("cleaned", result.cleanup_receipt.status.value)
            self.assertEqual(1, len(loop.records))
            leftovers = client.run((
                "ps", "--all", "--quiet", "--filter",
                f"label=fam.environment={result.plan.environment_id}",
            ))
            self.assertEqual(b"", leftovers.output.strip())

    def test_exact_natural_template_is_healthy_secret_bound_and_cleaned(self):
        client = DockerCommandClient(maximum_output_bytes=64 * 1024 * 1024)
        observed = client.run((
            "image", "inspect", "--format", "{{.Id}}", POSTGRESQL_IMAGE_REF,
        ))
        if observed.exit_code != 0:
            self.skipTest("cached PostgreSQL image is unavailable")
        self.assertEqual(
            f"sha256:{POSTGRESQL_IMAGE_SHA256}",
            observed.output.decode().strip(),
        )
        now = datetime.now(timezone.utc)
        prompt = (
            "Create the migration and run a PostgreSQL service end-to-end "
            "using PostgreSQL secret ref secret.postgres-natural."
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            owner = root / "owner"
            candidate_root = root / "candidate"
            owner.mkdir()
            candidate_root.mkdir()
            migration_root = candidate_root / "db"
            migration_root.mkdir()
            (migration_root / "001.up.sql").write_text(
                "CREATE TABLE example(id bigint primary key, note text NOT NULL);\n"
                "INSERT INTO example(id, note) VALUES (1, 'verified');\n",
                encoding="utf-8",
            )
            (migration_root / "001.down.sql").write_text(
                "DROP TABLE example;\n", encoding="utf-8",
            )
            entries = tuple(
                CandidateBaselineEntry(
                    path.relative_to(candidate_root).as_posix(),
                    CandidateEntryKind.FILE,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    path.stat().st_size,
                    False,
                )
                for path in sorted(migration_root.glob("*.sql"))
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=prompt, workspace_root=str(owner), owner_id="owner-1",
                principal_id="owner-1", task_id="task-postgresql",
                grant_id="grant-postgresql", toolchains=("sql",), now=now,
            )
            resource_grant = proposal.integration_resource_grant
            self.assertIsNotNone(resource_grant)
            candidate = CandidateWorkspace(
                "candidate-postgresql", "task-postgresql", "baseline-1",
                str(owner), str(candidate_root), now, "copy", "a" * 64, entries,
            )
            changed_paths = tuple(item.path for item in entries)
            plan = NaturalIntegrationEnvironmentPlanner("host-real").build(
                proposal.definition, candidate, changed_paths,
                "changeset-postgresql", (), postapply=False, now=now,
                resource_grant=resource_grant,
            )
            migration_plan = NaturalPostgreSQLVerificationPlanBuilder().build(
                proposal.definition,
                candidate,
                entries,
                changed_paths,
                plan,
                now=now,
            )
            secrets = _PostgreSQLSecrets()
            adapter = DockerIntegrationEnvironmentAdapter(
                secrets, client, health_recipes=ProductDockerHealthRecipes(client),
            )
            authority = _Authority(proposal.grant, resource_grant)
            service = IntegrationEnvironmentService(authority, adapter)
            result = service.start(
                plan, candidate, resource_grant.grant_id, "owner-1",
                "session-1", lambda: False,
            )
            try:
                self.assertEqual(
                    POSTGRESQL_IMAGE_SHA256,
                    result.receipt.services[0].image_sha256,
                )
                self.assertEqual(
                    (), result.receipt.services[0].allocated_ports,
                )
                self.assertEqual(("integration:postgresql",), tuple(secrets.consumers))
                self.assertEqual(
                    (EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE),
                    tuple(dict.fromkeys(item.authority for item in authority.requests)),
                )
                verification = PostgreSQLIntegrationVerificationService(
                    authority,
                    PostgreSQLIntegrationVerificationAdapter(
                        _Protector(), client,
                    ),
                ).execute(
                    migration_plan,
                    candidate,
                    plan,
                    result,
                    proposal.grant.grant_id,
                    resource_grant.grant_id,
                    "owner-1",
                    "session-1",
                    lambda: False,
                )
                self.assertTrue(verification.passed)
                self.assertEqual(
                    verification.baseline_schema_sha256,
                    verification.rollback_schema_sha256,
                )
                self.assertEqual(
                    verification.forward_data_sha256,
                    verification.reapplied_data_sha256,
                )
                self.assertEqual(
                    verification.baseline_data_sha256,
                    verification.restored_data_sha256,
                )
                backup = candidate_root / verification.backup_relative_path
                self.assertTrue(backup.read_bytes().startswith(b"protected:"))
            finally:
                cleaned = service.cleanup(
                    plan, candidate, result.receipt, result.permit,
                )
            self.assertEqual("cleaned", cleaned.status.value)
            leftovers = client.run((
                "ps", "--all", "--quiet", "--filter",
                f"label=fam.environment={plan.environment_id}",
            ))
            self.assertEqual(b"", leftovers.output.strip())


class _PostgreSQLSecrets:
    def __init__(self):
        self.consumers = []

    def environment(self, secret_refs, consumer_id):
        if secret_refs != ("secret.postgres-natural",):
            raise PermissionError("unexpected natural PostgreSQL secret")
        self.consumers.append(consumer_id)
        return {"POSTGRES_PASSWORD": "bounded-natural-password"}


class _Authority:
    def __init__(self, *grants):
        self.grants = {item.grant_id: item for item in grants}
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        grant = self.grants.get(request.grant_id)
        allowed = (
            grant is not None
            and request.authority in grant.authorities
            and request.task_id == grant.scope.scope_id
            and request.workspace_root in grant.scope.workspace_roots
            and (
                request.secret_ref is None
                or request.secret_ref in grant.scope.secret_refs
            )
            and (
                request.toolchain is None
                or request.toolchain in grant.scope.toolchains
            )
        )
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id,
            request.grant_id, request.authority, datetime.now(timezone.utc),
            allowed, "authorized" if allowed else "scope_mismatch",
        )


class _Protector:
    @staticmethod
    def encrypt(plaintext, context):
        if not context.startswith("fam-postgresql-backup:"):
            raise PermissionError("unexpected backup context")
        return b"protected:" + plaintext[::-1]

    @staticmethod
    def decrypt(ciphertext, context):
        if not context.startswith("fam-postgresql-backup:"):
            raise PermissionError("unexpected backup context")
        if not ciphertext.startswith(b"protected:"):
            raise PermissionError("backup is not protected")
        return ciphertext[len(b"protected:"):][::-1]


class _CoordinatorLoop:
    def __init__(self, candidate):
        self.candidate = candidate
        self.records = []

    def current_candidate(self, owner_id, task_id):
        return self.candidate

    def record_integration_environment(
        self, owner_id, task_id, plan, start, cleanup, *, postapply,
    ):
        self.records.append((plan, start, cleanup, postapply))


class _DirectEnvironments:
    def __init__(self, service):
        self.service = service
        self.values = {}

    def inspect(self, owner_id, environment_id):
        if environment_id not in self.values:
            raise KeyError(environment_id)
        return self.values[environment_id]

    def start(
        self, owner_id, plan, candidate, grant_id, principal_id, session_id,
        cancelled,
    ):
        result = self.service.start(
            plan, candidate, grant_id, principal_id, session_id, cancelled,
        )
        self.values[plan.environment_id] = SimpleNamespace(
            plan=plan, candidate=candidate, start_result=result,
            latest_receipt=result.receipt, state="active",
        )
        return result

    def cleanup(self, owner_id, environment_id):
        stored = self.values[environment_id]
        receipt = self.service.cleanup(
            stored.plan, stored.candidate, stored.latest_receipt,
            stored.start_result.permit,
        )
        self.values[environment_id] = SimpleNamespace(
            plan=stored.plan, candidate=stored.candidate,
            start_result=stored.start_result, latest_receipt=receipt,
            state="cleaned",
        )
        return receipt

    def for_task(self, owner_id, task_id):
        return tuple(
            item for item in self.values.values() if item.plan.task_id == task_id
        )


if __name__ == "__main__":
    unittest.main()
