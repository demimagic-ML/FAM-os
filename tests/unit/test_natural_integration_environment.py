import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.database import (
    NaturalPostgreSQLVerificationPlanBuilder,
    NaturalSQLitePlanBuilder,
)
from fam_os.adapters.integration import NaturalIntegrationEnvironmentPlanner
from fam_os.adapters.integration.postgresql_template import (
    POSTGRESQL_HEALTH_RECIPE_ID,
    POSTGRESQL_IMAGE_REF,
    POSTGRESQL_IMAGE_SHA256,
    POSTGRESQL_VOLUME_BYTES,
)
from fam_os.adapters.integration.secret_consumer import (
    integration_secret_consumer_id,
)
from fam_os.core.engineering import (
    CandidateBaselineEntry,
    CandidateEntryKind,
    CandidateWorkspace,
    EngineeringAuthority,
    IntegrationAllocatedPort,
    IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStartResult,
    IntegrationEnvironmentStatus,
    IntegrationExecutionPermit,
    IntegrationNetworkMode,
    IntegrationServiceReceipt,
    NaturalIntegrationEnvironmentDeclaration,
    NaturalIntegrationServiceDeclaration,
    NaturalIntegrationServiceTemplate,
    NaturalLanguageEngineeringPlanner,
    integration_environment_plan_digest,
)
from fam_os.schemas import SchemaValidationError, dumps_document
from fam_os.product.natural_engineering_integration import (
    NaturalEngineeringIntegrationCoordinator,
)
from fam_os.product.storage.integration_environment_repository import (
    StoredIntegrationEnvironment,
)


NOW = datetime(2026, 7, 19, 13, 0, tzinfo=timezone.utc)


class NaturalIntegrationEnvironmentTests(unittest.TestCase):
    def test_postgresql_migration_verifies_while_runtime_is_active_then_cleans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owner = (root / "owner").resolve()
            workspace = (root / "candidate").resolve()
            owner.mkdir()
            (workspace / "db").mkdir(parents=True)
            files = {
                "db/001.up.sql": "CREATE TABLE notes(id bigint);\n",
                "db/001.down.sql": "DROP TABLE notes;\n",
            }
            for relative, content in files.items():
                (workspace / relative).write_text(content, encoding="utf-8")
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=(
                    "Create a PostgreSQL migration and run a PostgreSQL service "
                    "using PostgreSQL secret ref secret.postgres-test."
                ),
                workspace_root=str(owner), owner_id="owner-1",
                principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("sql",), now=NOW,
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
                "candidate-1", "task-1", "baseline-1", str(owner),
                str(workspace), NOW, "copy", "a" * 64, entries,
            )
            loop = _Loop(candidate)
            environments = _Environments()
            verifier = _PostgreSQLVerifier(environments)
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43129,
                resource_grant_resolver=lambda identity: (
                    proposal.integration_resource_grant
                    if identity == proposal.integration_resource_grant.grant_id
                    else None
                ),
                postgresql_planner=NaturalPostgreSQLVerificationPlanBuilder(),
                postgresql_verifier=verifier,
            )

            result = coordinator.run_candidate(
                "owner-1", proposal.definition, candidate,
                tuple(files), "changeset-1", session_id="session-1",
                principal_id="owner-1",
            )

            self.assertTrue(verifier.observed_active)
            self.assertIsNotNone(result.postgresql_plan)
            self.assertTrue(result.postgresql_verification.passed)
            self.assertEqual("cleaned", result.cleanup_receipt.status.value)

    def test_postgresql_verification_failure_still_cleans_and_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _postgresql_candidate(Path(temporary))
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=definition.task.intent,
                workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("sql",), now=NOW,
            )
            loop, environments = _Loop(candidate), _Environments()
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43129,
                resource_grant_resolver=lambda _identity: (
                    proposal.integration_resource_grant
                ),
                postgresql_planner=NaturalPostgreSQLVerificationPlanBuilder(),
                postgresql_verifier=_FailingPostgreSQLVerifier(),
            )
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                coordinator.run_candidate(
                    "owner-1", proposal.definition, candidate,
                    tuple(item.path for item in candidate.entries),
                    "changeset-1", session_id="session-1",
                    principal_id="owner-1",
                )
            stored = next(iter(environments.values.values()))
            self.assertEqual("cleaned", stored.state)
            self.assertEqual([], loop.records)

    def test_postapply_postgresql_reuses_exact_applied_migration_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _postgresql_candidate(Path(temporary))
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=definition.task.intent,
                workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("sql",), now=NOW,
            )
            loop, environments = _Loop(candidate), _Environments()
            loop.changesets = (SimpleNamespace(
                changeset_id="changeset-1",
                status=SimpleNamespace(value="applied"),
                operations=tuple(
                    SimpleNamespace(path=item.path, source_path=None)
                    for item in candidate.entries
                ),
            ),)
            verifier = _PostgreSQLVerifier(environments)
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43129,
                resource_grant_resolver=lambda _identity: (
                    proposal.integration_resource_grant
                ),
                postgresql_planner=NaturalPostgreSQLVerificationPlanBuilder(),
                postgresql_verifier=verifier,
            )

            result = coordinator.run_postapply(
                "owner-1", proposal.definition, "changeset-1",
                session_id="session-1", principal_id="owner-1",
            )

            self.assertTrue(result.postapply)
            self.assertTrue(result.postgresql_verification.passed)
            self.assertIn("postapply", result.postgresql_plan.service_id)
            self.assertEqual("cleaned", result.cleanup_receipt.status.value)

    def test_static_preview_is_planned_started_cleaned_bound_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(Path(temporary), "candidate-1")
            loop = _Loop(candidate)
            environments = _Environments()
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43129,
            )
            result = coordinator.run_candidate(
                "owner-1", definition, candidate, ("index.html",),
                "changeset-1", session_id="session-1",
                principal_id="owner-1",
            )

            self.assertEqual("cleaned", result.cleanup_receipt.status.value)
            self.assertEqual("/index.html", result.plan.services[0].health_check.path)
            self.assertEqual(
                "integration.python.static-http@1.0.0",
                result.plan.services[0].signed_launch_recipe_id,
            )
            self.assertEqual(1, environments.start_count)
            self.assertEqual(result.cleanup_receipt.receipt_id, loop.records[-1][2])

            replay = coordinator.run_candidate(
                "owner-1", definition, candidate, ("index.html",),
                "changeset-1", session_id="session-1",
                principal_id="owner-1",
            )
            self.assertEqual(result.cleanup_receipt, replay.cleanup_receipt)
            self.assertEqual(1, environments.start_count)

    def test_postapply_uses_fresh_owner_clone_and_distinct_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _candidate, definition = _values(root, "candidate-1")
            fresh, _unused = _values(root, "candidate-postapply", name="fresh")
            loop = _Loop(fresh)
            environments = _Environments()
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43130,
            )
            result = coordinator.run_postapply(
                "owner-1", definition, "changeset-1",
                session_id="session-1", principal_id="owner-1",
            )

            self.assertTrue(result.postapply)
            self.assertEqual(fresh.candidate_id, result.plan.candidate_id)
            self.assertIn("postapply", result.plan.environment_id)
            self.assertTrue(loop.records[-1][-1])

    def test_non_html_candidate_cannot_claim_static_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="app.py",
            )
            with self.assertRaisesRegex(LookupError, "HTML"):
                NaturalIntegrationEnvironmentPlanner("host-1").build(
                    definition, candidate, ("app.py",), "changeset-1", 43131,
                    postapply=False, now=NOW,
                )

    def test_full_stack_request_uses_two_fixed_signed_templates_in_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1",
                prompt="Update the API and page, then run the full-stack app end-to-end.",
                extra_files={"api.py": "# accepts the exact port argument\n"},
            )
            planner = NaturalIntegrationEnvironmentPlanner("host-1")
            self.assertEqual(
                2,
                planner.required_port_count(
                    definition, candidate, ("api.py", "index.html"),
                ),
            )
            plan = planner.build(
                definition, candidate, ("api.py", "index.html"),
                "changeset-1", (43132, 43133), postapply=False, now=NOW,
            )

            self.assertEqual(
                ("python-api-candidate", "static-preview-candidate"),
                tuple(item.service_id for item in plan.services),
            )
            self.assertEqual(
                "integration.python.root-api@1.0.0",
                plan.services[0].signed_launch_recipe_id,
            )
            self.assertEqual(("/workspace/api.py", "43132"), plan.services[0].launch_arguments)
            self.assertEqual(
                ("python-api-candidate",), plan.services[1].dependency_ids,
            )
            self.assertEqual((43132, 43133), tuple(
                service.ports[0].requested_host_port for service in plan.services
            ))

    def test_api_template_requires_regular_root_entrypoint_and_unique_ports(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="api.py",
                prompt="Update the API and run it end-to-end.",
            )
            planner = NaturalIntegrationEnvironmentPlanner("host-1")
            plan = planner.build(
                definition, candidate, ("api.py",), "changeset-1", 43134,
                postapply=False, now=NOW,
            )
            self.assertEqual(("python-api-candidate",), tuple(
                item.service_id for item in plan.services
            ))

            (Path(candidate.candidate_workspace) / "index.html").write_text(
                "<h1>FAM</h1>\n",
            )
            with self.assertRaisesRegex(ValueError, "unique port"):
                planner.build(
                    definition, candidate, ("api.py", "index.html"),
                    "changeset-1", (43134, 43134),
                    postapply=False, now=NOW,
                )

    def test_api_only_request_does_not_implicitly_run_an_unrequested_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="api.py",
                prompt="Update the API and run it end-to-end.",
                extra_files={"index.html": "<h1>Unrequested</h1>\n"},
            )
            plan = NaturalIntegrationEnvironmentPlanner("host-1").build(
                definition, candidate, ("api.py",), "changeset-1", 43140,
                postapply=False, now=NOW,
            )
            self.assertEqual(("python-api-candidate",), tuple(
                item.service_id for item in plan.services
            ))

    def test_coordinator_allocates_and_records_every_full_stack_service(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1",
                prompt="Update the API and page, then run the full-stack app end-to-end.",
                extra_files={"api.py": "# accepts the exact port argument\n"},
            )
            loop = _Loop(candidate)
            environments = _Environments()
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW,
                port_allocator=iter((43135, 43136)).__next__,
            )
            result = coordinator.run_candidate(
                "owner-1", definition, candidate,
                ("api.py", "index.html"), "changeset-1",
                session_id="session-1", principal_id="owner-1",
            )
            self.assertEqual(2, len(result.start_result.receipt.services))
            self.assertEqual(1, environments.start_count)

    def test_separately_approved_resources_are_exactly_attached(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = (
                "Update the API and run it end-to-end with network access to "
                "api.example.com:443 using secret ref database/password."
            )
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="api.py",
                prompt=prompt,
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=prompt, workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("html",), now=NOW,
            )
            resource = proposal.integration_resource_grant
            self.assertIsNotNone(resource)
            loop = _Loop(candidate)
            environments = _Environments()
            coordinator = NaturalEngineeringIntegrationCoordinator(
                loop, environments,
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43141,
                resource_grant_resolver=lambda grant_id: (
                    resource if grant_id == resource.grant_id else None
                ),
            )
            result = coordinator.run_candidate(
                "owner-1", definition, candidate, ("api.py",), "changeset-1",
                session_id="session-1", principal_id="owner-1",
            )

            self.assertEqual(IntegrationNetworkMode.ALLOWLIST, result.plan.network_mode)
            self.assertEqual(("api.example.com:443",), result.plan.network_hosts)
            self.assertEqual(
                (
                    EngineeringAuthority.EXECUTE,
                    EngineeringAuthority.NETWORK,
                    EngineeringAuthority.SECRET_USE,
                ),
                result.plan.required_authorities,
            )
            self.assertEqual(
                ("database/password",), result.plan.services[0].secret_refs,
            )
            self.assertEqual(resource.grant_id, environments.last_grant_id)

    def test_resource_intent_without_an_approved_grant_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="api.py",
                prompt=(
                    "Update the API and run it end-to-end with network access "
                    "to api.example.com:443."
                ),
            )
            coordinator = NaturalEngineeringIntegrationCoordinator(
                _Loop(candidate), _Environments(),
                NaturalIntegrationEnvironmentPlanner("host-1"),
                clock=lambda: NOW, port_allocator=lambda: 43142,
            )
            with self.assertRaisesRegex(PermissionError, "separate owner"):
                coordinator.run_candidate(
                    "owner-1", definition, candidate, ("api.py",),
                    "changeset-1", session_id="session-1",
                    principal_id="owner-1",
                )

    def test_resource_grant_cannot_expand_the_natural_endpoint_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = (
                "Update the API and run it end-to-end with network access to "
                "api.example.com:443."
            )
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="api.py",
                prompt=prompt,
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=prompt, workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("html",), now=NOW,
            )
            resource = proposal.integration_resource_grant
            widened = replace(
                resource,
                scope=replace(
                    resource.scope,
                    network_hosts=(
                        "api.example.com:443", "unrequested.example:443",
                    ),
                ),
            )
            planner = NaturalIntegrationEnvironmentPlanner("host-1")
            with self.assertRaisesRegex(PermissionError, "differs from exact intent"):
                planner.build(
                    definition, candidate, ("api.py",), "changeset-1", 43143,
                    postapply=False, now=NOW, resource_grant=widened,
                )

    def test_postgresql_uses_one_fixed_container_and_opaque_password_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = (
                "Create the migration and run a PostgreSQL service end-to-end "
                "using PostgreSQL secret ref secret.postgres-test."
            )
            candidate, definition = _values(
                Path(temporary), "candidate-1", filename="migration.sql",
                prompt=prompt,
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=prompt, workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("sql",), now=NOW,
            )
            planner = NaturalIntegrationEnvironmentPlanner("host-1")

            self.assertFalse(NaturalSQLitePlanBuilder.requested(prompt))
            self.assertEqual(
                0, planner.required_port_count(
                    definition, candidate, ("migration.sql",),
                ),
            )
            plan = planner.build(
                definition, candidate, ("migration.sql",), "changeset-1", (),
                postapply=False, now=NOW,
                resource_grant=proposal.integration_resource_grant,
            )

            self.assertEqual(("postgresql-candidate",), tuple(
                item.service_id for item in plan.services
            ))
            service = plan.services[0]
            self.assertEqual(POSTGRESQL_IMAGE_REF, service.image_ref)
            self.assertEqual(POSTGRESQL_IMAGE_SHA256, service.image_sha256)
            self.assertEqual((), service.ports)
            self.assertEqual(
                POSTGRESQL_HEALTH_RECIPE_ID,
                service.health_check.signed_recipe_id,
            )
            self.assertEqual(("secret.postgres-test",), service.secret_refs)
            self.assertEqual(
                "integration:postgresql",
                integration_secret_consumer_id(service),
            )
            self.assertEqual(POSTGRESQL_VOLUME_BYTES, service.volumes[0].maximum_bytes)
            self.assertEqual(POSTGRESQL_VOLUME_BYTES, plan.resource_impact.max_changed_bytes)
            self.assertEqual(64, plan.resource_impact.max_processes)
            self.assertEqual(
                (EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE),
                plan.required_authorities,
            )

    def test_postgresql_requires_an_exact_secret_and_multi_service_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = (
                "Update the migration and run a PostgreSQL service end-to-end."
            )
            candidate, definition = _values(
                root, "candidate-missing", filename="migration.sql",
                prompt=missing, name="candidate-missing",
            )
            with self.assertRaisesRegex(PermissionError, "explicit opaque"):
                NaturalIntegrationEnvironmentPlanner("host-1").build(
                    definition, candidate, ("migration.sql",), "changeset-1", (),
                    postapply=False, now=NOW,
                )

            ambiguous = (
                "Update the API and run it end-to-end with a PostgreSQL service "
                "using secret ref secret.shared."
            )
            candidate, definition = _values(
                root, "candidate-ambiguous", filename="api.py",
                prompt=ambiguous, name="candidate-ambiguous",
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=ambiguous, workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("python",), now=NOW,
            )
            with self.assertRaisesRegex(PermissionError, "explicit service role"):
                NaturalIntegrationEnvironmentPlanner("host-1").build(
                    definition, candidate, ("api.py",), "changeset-1", (43144,),
                    postapply=False, now=NOW,
                    resource_grant=proposal.integration_resource_grant,
                )

            scoped = (
                "Update the API and run it end-to-end with a PostgreSQL service "
                "using API secret ref secret.api and PostgreSQL secret ref "
                "secret.postgres."
            )
            candidate, definition = _values(
                root, "candidate-scoped", filename="api.py", prompt=scoped,
                name="candidate-scoped",
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=scoped, workspace_root=candidate.owner_workspace,
                owner_id="owner-1", principal_id="owner-1", task_id="task-1",
                grant_id="grant-1", toolchains=("python",), now=NOW,
            )
            plan = NaturalIntegrationEnvironmentPlanner("host-1").build(
                definition, candidate, ("api.py",), "changeset-1", (43145,),
                postapply=False, now=NOW,
                resource_grant=proposal.integration_resource_grant,
            )
            self.assertEqual(
                ("secret.postgres",), plan.services[0].secret_refs,
            )
            self.assertEqual(("secret.api",), plan.services[1].secret_refs)
            self.assertEqual(
                "integration:python-api",
                integration_secret_consumer_id(plan.services[1]),
            )
            self.assertEqual(
                ("postgresql-candidate",), plan.services[1].dependency_ids,
            )
            postapply = NaturalIntegrationEnvironmentPlanner("host-1").build(
                definition, candidate, (), "changeset-1", (43146,),
                postapply=True, now=NOW,
                resource_grant=proposal.integration_resource_grant,
            )
            self.assertEqual(
                "integration:postgresql",
                integration_secret_consumer_id(postapply.services[0]),
            )
            self.assertEqual(
                "integration:python-api",
                integration_secret_consumer_id(postapply.services[1]),
            )

            widened = replace(
                proposal.integration_resource_grant,
                resource_impact=replace(
                    proposal.integration_resource_grant.resource_impact,
                    max_changed_bytes=(
                        proposal.integration_resource_grant.resource_impact.max_changed_bytes
                        + 1
                    ),
                ),
            )
            with self.assertRaisesRegex(PermissionError, "differs from exact intent"):
                NaturalIntegrationEnvironmentPlanner("host-1").build(
                    definition, candidate, ("api.py",), "changeset-1", (43145,),
                    postapply=False, now=NOW, resource_grant=widened,
                )

    def test_versioned_declaration_controls_only_logical_ids_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1",
                prompt="Update the API and page, then run the full-stack app end-to-end.",
                extra_files={"api.py": "# exact root API\n"},
            )
            declaration = NaturalIntegrationEnvironmentDeclaration(
                "declared-preview",
                (
                    NaturalIntegrationServiceDeclaration(
                        "backend", NaturalIntegrationServiceTemplate.PYTHON_API,
                        (),
                    ),
                    NaturalIntegrationServiceDeclaration(
                        "frontend", NaturalIntegrationServiceTemplate.STATIC_SITE,
                        ("backend",),
                    ),
                ),
            )
            (Path(candidate.candidate_workspace) / "fam.integration.json").write_text(
                dumps_document(declaration), encoding="utf-8",
            )
            plan = NaturalIntegrationEnvironmentPlanner("host-1").build(
                definition, candidate,
                ("api.py", "index.html", "fam.integration.json"),
                "changeset-1", (43137, 43138), postapply=False, now=NOW,
            )

            self.assertEqual(
                ("backend-candidate", "frontend-candidate"),
                tuple(item.service_id for item in plan.services),
            )
            self.assertEqual(
                ("backend-candidate",), plan.services[1].dependency_ids,
            )
            self.assertEqual(
                ("integration.python.root-api@1.0.0",
                 "integration.python.static-http@1.0.0"),
                tuple(item.signed_launch_recipe_id for item in plan.services),
            )

    def test_declaration_cannot_expand_intent_or_bypass_strict_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            candidate, definition = _values(
                Path(temporary), "candidate-1",
                extra_files={"api.py": "# should not run\n"},
            )
            declaration = NaturalIntegrationEnvironmentDeclaration(
                "overreach",
                (NaturalIntegrationServiceDeclaration(
                    "api", NaturalIntegrationServiceTemplate.PYTHON_API, (),
                ),),
            )
            path = Path(candidate.candidate_workspace) / "fam.integration.json"
            path.write_text(dumps_document(declaration), encoding="utf-8")
            planner = NaturalIntegrationEnvironmentPlanner("host-1")
            with self.assertRaisesRegex(PermissionError, "exceeds"):
                planner.build(
                    definition, candidate, ("fam.integration.json",),
                    "changeset-1", 43139, postapply=False, now=NOW,
                )

            duplicate = dumps_document(declaration).replace(
                '"declaration_id":',
                '"declaration_id":"duplicate","declaration_id":', 1,
            )
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(SchemaValidationError):
                planner.build(
                    definition, candidate, ("fam.integration.json",),
                    "changeset-1", 43139, postapply=False, now=NOW,
                )

    def test_declaration_rejects_duplicate_templates_and_dependency_cycles(self):
        duplicate = (
            NaturalIntegrationServiceDeclaration(
                "one", NaturalIntegrationServiceTemplate.STATIC_SITE, (),
            ),
            NaturalIntegrationServiceDeclaration(
                "two", NaturalIntegrationServiceTemplate.STATIC_SITE, (),
            ),
        )
        with self.assertRaisesRegex(ValueError, "cannot repeat"):
            NaturalIntegrationEnvironmentDeclaration("duplicate", duplicate)
        cycle = (
            NaturalIntegrationServiceDeclaration(
                "api", NaturalIntegrationServiceTemplate.PYTHON_API, ("web",),
            ),
            NaturalIntegrationServiceDeclaration(
                "web", NaturalIntegrationServiceTemplate.STATIC_SITE, ("api",),
            ),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            NaturalIntegrationEnvironmentDeclaration("cycle", cycle)


class _Loop:
    def __init__(self, fresh):
        self.fresh = fresh
        self.records = []
        self.changesets = ()

    def record_integration_environment(
        self, owner_id, task_id, plan, start, cleanup, *, postapply,
    ):
        self.records.append((owner_id, task_id, cleanup.receipt_id, postapply))

    def fresh_owner_candidate(self, owner_id, task_id):
        return self.fresh

    def current_candidate(self, owner_id, task_id):
        return self.fresh

    def candidate_changesets(self, owner_id, task_id):
        return self.changesets


class _Environments:
    def __init__(self):
        self.values = {}
        self.start_count = 0
        self.last_grant_id = None

    def inspect(self, owner_id, environment_id):
        if environment_id not in self.values:
            raise KeyError(environment_id)
        return self.values[environment_id]

    def for_task(self, owner_id, task_id):
        return tuple(
            item for item in self.values.values()
            if item.plan.task_id == task_id
        )

    def start(
        self, owner_id, plan, candidate, grant_id, principal_id, session_id,
        cancelled,
    ):
        self.start_count += 1
        self.last_grant_id = grant_id
        permit = IntegrationExecutionPermit(
            f"permit-{plan.environment_id}", plan.environment_id,
            plan.approved_changeset_id, plan.exact_host_id, ("decision-1",),
            NOW, NOW + timedelta(minutes=5),
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
            NOW, NOW + timedelta(seconds=1), service_receipts, (), (),
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
            completed_at=NOW + timedelta(seconds=2),
            cleanup_evidence_ids=(f"stopped-{environment_id}",),
        )
        self.values[environment_id] = replace(
            stored, latest_receipt=cleaned, state="cleaned",
        )
        return cleaned


class _PostgreSQLVerifier:
    def __init__(self, environments):
        self.environments = environments
        self.observed_active = False

    def execute(self, plan, candidate, environment, start, *args):
        self.observed_active = (
            self.environments.values[environment.environment_id].state == "active"
        )
        return SimpleNamespace(
            passed=True, receipt_id="postgresql-verification-1",
        )


class _FailingPostgreSQLVerifier:
    def execute(self, *args, **kwargs):
        raise RuntimeError("verification failed")


def _postgresql_candidate(root):
    owner = (root / "owner").resolve()
    workspace = (root / "candidate").resolve()
    owner.mkdir()
    (workspace / "db").mkdir(parents=True)
    contents = {
        "db/001.up.sql": "CREATE TABLE notes(id bigint);\n",
        "db/001.down.sql": "DROP TABLE notes;\n",
    }
    for relative, content in contents.items():
        (workspace / relative).write_text(content, encoding="utf-8")
    proposal = NaturalLanguageEngineeringPlanner().propose(
        prompt=(
            "Create a PostgreSQL migration and run a PostgreSQL service using "
            "PostgreSQL secret ref secret.postgres-test."
        ),
        workspace_root=str(owner), owner_id="owner-1", principal_id="owner-1",
        task_id="task-1", grant_id="grant-1", toolchains=("sql",), now=NOW,
    )
    entries = tuple(
        CandidateBaselineEntry(
            relative, CandidateEntryKind.FILE,
            hashlib.sha256(content.encode()).hexdigest(), len(content.encode()),
            False,
        )
        for relative, content in sorted(contents.items())
    )
    return CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", str(owner), str(workspace),
        NOW, "copy", "a" * 64, entries,
    ), proposal.definition


def _values(
    root: Path, candidate_id: str, *, filename="index.html", name="candidate",
    prompt="Update index.html and preview the site end-to-end.",
    extra_files=None,
):
    workspace = (root / name).resolve()
    workspace.mkdir()
    content = "<h1>FAM</h1>\n" if filename.endswith(".html") else "VALUE = 1\n"
    (workspace / filename).write_text(content)
    for relative, value in (extra_files or {}).items():
        (workspace / relative).write_text(value)
    owner = (root / "owner").resolve()
    owner.mkdir(exist_ok=True)
    proposal = NaturalLanguageEngineeringPlanner().propose(
        prompt=prompt,
        workspace_root=str(owner), owner_id="owner-1",
        principal_id="owner-1", task_id="task-1", grant_id="grant-1",
        toolchains=("html",), now=NOW,
    )
    entry = CandidateBaselineEntry(
        filename, CandidateEntryKind.FILE,
        hashlib.sha256(content.encode()).hexdigest(), len(content), False,
    )
    candidate = CandidateWorkspace(
        candidate_id, "task-1", f"baseline-{candidate_id}", str(owner),
        str(workspace), NOW, "copy", "a" * 64, (entry,),
    )
    return candidate, proposal.definition


if __name__ == "__main__":
    unittest.main()
