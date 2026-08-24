"""Signed recipes, sandbox, dependency, admin, and secret authority tests."""

import base64
from dataclasses import replace
from datetime import timedelta
import hashlib
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.bubblewrap.engineering import (
    EngineeringSandboxAdapter, toolchain_tree_sha256,
)
from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier, sign_recipe_specification,
)
from fam_os.adapters.dependencies import IsolatedDependencyResolverAdapter
from fam_os.adapters.registry.engineering_licenses import SpdxLicensePolicyAdapter
from fam_os.adapters.linux.raw_shell import RawShellExecutionAdapter
from fam_os.adapters.linux.bounded_command import BoundedCommandResult
from fam_os.core.engineering import (
    CandidateWorkspace, DependencyResolutionBudget, DependencyResolutionReceipt,
    DependencyResolutionRequest, DependencyResolutionStatus,
    EngineeringEcosystem, EngineeringSandboxProfile,
    HostAdministrationChangeSet, HostAdministrationMechanism,
    HostAdministrationReceipt, HostChangeStatus,
    LanguageToolQualification, RawShellAuthorization, RawShellPrivilegeTier,
    PolyglotQualificationService,
    EngineeringSecretService,
    EngineeringHostAdministrationService,
    SandboxNetworkMode, SbomComponent, SecretUseAuthorization, SecretUseLevel,
    SignedToolRecipe, ToolQualificationStatus, ToolRecipePurpose,
    ToolchainMount, ToolchainMountSourceKind,
    SecretExposurePolicy,
)
from fam_os.core.engineering.dependency_policy import DependencyAdmissionPolicy
from fam_os.core.engineering.execution_policy import RawShellGate, SignedToolRecipeCatalog, signed_recipe_payload
from fam_os.core.engineering.production_recipes import (
    ToolRecipeSpecification, initial_recipe_specifications,
)
from fam_os.core.engineering.recipe_matrix import REQUIRED_PURPOSES
from fam_os.core.engineering.privileged_policy import HostAdministrationGate, SecretUseGate
from fam_os.verification.sandbox import IsolationLevel, SandboxResult, SandboxStatus
from fam_os.verification.engineering import SignedEngineeringReceiptVerifier
from tests.contract.schema_engineering_fixtures import (
    NOW, engineering_grant_schema_values, engineering_schema_values,
)
from tests.contract.schema_execution_fixtures import execution_schema_values


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def signed_recipe(private_key, *, purpose=ToolRecipePurpose.TYPE_CHECK):
    dummy_signature = base64.b64encode(b"\0" * 64).decode()
    unsigned = SignedToolRecipe(
        "python-compile", "1.0.0", EngineeringEcosystem.PYTHON, purpose,
        "/usr/bin/python3", ("-m", "py_compile", "src/main.py"), ("PATH",),
        (0,), ("verifier.python.compile",), "recipe-key", "0" * 64,
        dummy_signature,
    )
    payload = signed_recipe_payload(unsigned)
    return replace(
        unsigned, payload_sha256=sha(payload),
        signature_base64=base64.b64encode(private_key.sign(payload)).decode(),
    )


class FakeLauncher:
    def __init__(self, exit_code=0, stderr=None):
        self.exit_code = exit_code
        self.stderr = stderr
        self.calls = []

    def run(self, command, limits, environment, isolation):
        self.calls.append((command, limits, environment, isolation))
        return SandboxResult(
            SandboxStatus.COMPLETED, IsolationLevel.BUBBLEWRAP, 0.1,
            "ok" if self.exit_code == 0 else "",
            self.stderr if self.stderr is not None else (
                "" if self.exit_code == 0 else "bad fixture"
            ),
            self.exit_code,
        )


class FakeCommandRunner:
    def __init__(self):
        self.calls = []

    def run(self, command, cwd=None, environment=None):
        self.calls.append((command, cwd, environment))
        return BoundedCommandResult(0, "approved output", "")


class FakeAuthenticator:
    def verify(self, owner_id, authentication_context_id):
        return owner_id == "owner-1" and authentication_context_id == "interactive-owner-auth"


class FakeHostBroker:
    def __init__(self):
        self.calls = []

    def apply(self, change_set, authentication_context_id):
        self.calls.append((change_set, authentication_context_id))
        return HostAdministrationReceipt(
            "host-receipt-1", change_set.change_set_id, "external-root-broker",
            authentication_context_id, HostChangeStatus.APPLIED, NOW,
            NOW + timedelta(seconds=1), change_set.before_evidence_ids,
            ("host-after-1",), change_set.predicted_effects, (), 0, "a" * 64,
        )


class FakeSecretProvider:
    def use_opaque(self, secret_ref, consumer_id):
        return "opaque operation completed"

    def transform_redacted(self, secret_ref, consumer_id):
        return "account ****1234", "redaction-1"

    def disclose(self, secret_ref, consumer_id):
        return "plaintext-secret"


class FakeArtifactFetcher:
    def fetch(self, registry_url, hosts, packages, limit):
        if registry_url != "https://pypi.org/simple" or hosts != ("pypi.org",):
            raise PermissionError("unapproved dependency source")
        if packages != ("example",):
            raise PermissionError("package-name confusion detected")
        return (("example-1.0.whl", b"bounded-wheel"),)


class FakeCandidateInstaller:
    def install(self, root, environment, artifacts, ecosystem, wall_seconds):
        self.root = root
        environment.mkdir(parents=True)
        (environment / "installed.txt").write_text("example==1.0\n")
        (root / "requirements.lock").write_text("example==1.0\n")


class FakeDependencyInspector:
    def inspect(self, root, environment, ecosystem):
        return ((SbomComponent(
            "pkg:pypi/example@1.0", "example", "1.0", "e" * 64,
            "MIT", True,
        ),), (), ("license-mit",))


class EngineeringExecutionTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        verifier = Ed25519RecipeSignatureVerifier({
            "recipe-key": self.private_key.public_key(),
        })
        self.catalog = SignedToolRecipeCatalog(verifier)
        self.recipe = signed_recipe(self.private_key)
        self.catalog.admit(self.recipe)
        self.grant = engineering_grant_schema_values()[0]
        self.task = replace(
            engineering_schema_values()[0], grant_id=self.grant.grant_id,
        )

    def test_signed_recipe_rejects_semantic_tampering(self):
        self.assertEqual(self.recipe, self.catalog.get("python-compile", "1.0.0"))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.catalog.admit(replace(self.recipe, purpose=ToolRecipePurpose.TEST))

    def test_polyglot_matrix_requires_every_language_and_appropriate_recipe_family(self):
        matrix = execution_schema_values()[5]
        self.assertEqual(set(EngineeringEcosystem), {
            item.ecosystem for item in matrix.qualifications
        })
        without_css_lint = tuple(
            item for item in matrix.recipes
            if not (
                item.ecosystem is EngineeringEcosystem.CSS
                and item.purpose is ToolRecipePurpose.LINT
            )
        )
        with self.assertRaisesRegex(ValueError, "incomplete"):
            replace(matrix, recipes=without_css_lint)

    def test_release_recipe_specs_cover_every_required_gate_and_are_signable(self):
        specifications = initial_recipe_specifications()
        expected = sum(len(value) for value in REQUIRED_PURPOSES.values())
        self.assertEqual(expected, len(specifications))
        signed = tuple(
            sign_recipe_specification(item, "recipe-key", self.private_key)
            for item in specifications
        )
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "recipe-key": self.private_key.public_key(),
        }))
        for recipe in signed:
            catalog.admit(recipe)
        self.assertTrue(all(item.verifier_ids for item in signed))

    def test_candidate_sandbox_has_no_network_home_credentials_or_git_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve() / "candidate"
            (workspace / "src").mkdir(parents=True)
            (workspace / "src/main.py").write_text("value: int = 1\n")
            candidate = CandidateWorkspace(
                "candidate-exec", "task-1", "baseline-1", "/owner", str(workspace),
                NOW, "full_copy_fallback", "a" * 64, (),
            )
            profile = EngineeringSandboxProfile(
                "sandbox-1", 256 * 1024**2, 2, 10, 8, 16_384, 1024**2,
                SandboxNetworkMode.DENIED, (), (("PATH", "/usr/bin:/bin"),),
            )
            launcher = FakeLauncher()
            adapter = EngineeringSandboxAdapter(self.catalog, launcher=launcher)
            receipt = adapter.run("task-1", candidate, "python-compile", "1.0.0", profile)
            self.assertEqual(ToolQualificationStatus.PASSED, receipt.status)
            verdict = SignedEngineeringReceiptVerifier(self.catalog).verify(
                receipt, "1.0.0",
            )
            self.assertTrue(verdict.passed)
            command = launcher.calls[0][0]
            self.assertIn("--unshare-all", command)
            self.assertIn("--clearenv", command)
            self.assertIn("MemorySwapMax=0", command)
            self.assertNotIn(str(Path.home()), command)
            self.assertEqual((), receipt.network_destinations)
            self.assertEqual((0,), self.recipe.expected_exit_codes)

            profiled = EngineeringSandboxAdapter(
                self.catalog, launcher=FakeLauncher(),
                apparmor_profile="fam-os-userns",
            ).build_command(workspace, self.recipe, profile)
            self.assertIn("--scope", profiled)
            self.assertIn("--collect", profiled)
            self.assertNotIn("--pipe", profiled)
            self.assertNotIn("--wait", profiled)
            self.assertIn("/usr/bin/aa-exec", profiled)
            self.assertIn("fam-os-userns", profiled)

            failing = FakeLauncher(exit_code=1)
            failed = EngineeringSandboxAdapter(self.catalog, launcher=failing).run(
                "task-1", candidate, "python-compile", "1.0.0", profile,
            )
            self.assertEqual(ToolQualificationStatus.FAILED, failed.status)

            unavailable = EngineeringSandboxAdapter(
                self.catalog,
                launcher=FakeLauncher(
                    exit_code=1,
                    stderr=(
                        "bwrap: loopback: Failed RTM_NEWADDR: "
                        "Operation not permitted"
                    ),
                ),
            ).run("task-1", candidate, "python-compile", "1.0.0", profile)
            self.assertEqual(ToolQualificationStatus.UNAVAILABLE, unavailable.status)
            self.assertIn("required namespaces", unavailable.diagnostic)

    def test_installed_release_mount_resolves_only_digest_bound_expert_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "share/expert/toolchains/diagnostics/tool.py"
            source.parent.mkdir(parents=True)
            source.write_text("print('diagnostic')\n")
            mount = ToolchainMount(
                "share/expert/toolchains/diagnostics/tool.py",
                "/opt/fam/toolchains/diagnostics/tool.py",
                toolchain_tree_sha256(source),
                ToolchainMountSourceKind.INSTALLED_RELEASE,
            )
            specification = ToolRecipeSpecification(
                EngineeringEcosystem.PYTHON, ToolRecipePurpose.STACK_TRACE,
                "/usr/bin/python3",
                ("/opt/fam/toolchains/diagnostics/tool.py",),
                "verifier.runtime.stack.v1",
            )
            recipe = sign_recipe_specification(
                specification, "recipe-key", self.private_key,
                toolchain_mounts=(mount,),
            )
            catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
                "recipe-key": self.private_key.public_key(),
            }))
            catalog.admit(recipe)
            candidate = root / "candidate"
            candidate.mkdir()
            profile = EngineeringSandboxProfile(
                "sandbox-release-mount", 256 * 1024**2, 2, 10, 8,
                16_384, 1024**2, SandboxNetworkMode.DENIED, (), (),
            )
            adapter = EngineeringSandboxAdapter(
                catalog, launcher=FakeLauncher(), release_root=root,
            )
            command = adapter.build_command(candidate, recipe, profile)
            self.assertIn(str(source), command)
            self.assertIn(mount.sandbox_path, command)
            source.write_text("tampered\n")
            with self.assertRaisesRegex(PermissionError, "digest changed"):
                adapter.build_command(candidate, recipe, profile)

    def test_raw_shell_requires_exact_single_use_command_task_workspace_and_principal(self):
        command = b"printf '%s\\n' approved"
        authorization = RawShellAuthorization(
            "raw-shell-1", self.grant.grant_id, "task-1", self.grant.principal_id,
            "/workspace", "/usr/bin/bash", sha(command), (("PATH", "/usr/bin:/bin"),),
            RawShellPrivilegeTier.HOST_USER, NOW, NOW + timedelta(minutes=5),
        )
        gate = RawShellGate()
        gate.authorize(
            authorization, self.grant, command, principal_id=self.grant.principal_id,
            task_id="task-1", workspace_root="/workspace",
            instant=NOW + timedelta(minutes=1),
        )
        with self.assertRaises(PermissionError):
            gate.authorize(
                authorization, self.grant, b"different",
                principal_id=self.grant.principal_id, task_id="task-1",
                workspace_root="/workspace", instant=NOW + timedelta(minutes=1),
            )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            scoped = replace(
                authorization, workspace_root=str(workspace),
                issued_at=NOW - timedelta(minutes=1),
            )
            scoped_grant = replace(
                self.grant,
                scope=replace(
                    self.grant.scope, workspace_roots=(str(workspace),),
                ),
            )
            runner = FakeCommandRunner()
            adapter = RawShellExecutionAdapter(
                runner=runner, clock=lambda: NOW,
            )
            receipt = adapter.run(
                scoped, scoped_grant, command,
                principal_id=self.grant.principal_id, task_id="task-1",
                workspace_root=workspace, candidate_id="candidate-1",
            )
            self.assertEqual(ToolQualificationStatus.PASSED, receipt.status)
            self.assertEqual(("/usr/bin/bash", "-c", command.decode()), runner.calls[0][0])
            with self.assertRaisesRegex(PermissionError, "consumed"):
                adapter.run(
                    scoped, scoped_grant, command,
                    principal_id=self.grant.principal_id, task_id="task-1",
                    workspace_root=workspace, candidate_id="candidate-1",
                )

    def test_dependency_admission_is_project_local_budgeted_and_supply_chain_checked(self):
        request = DependencyResolutionRequest(
            "dependency-1", "task-1", "candidate-1", "python3",
            ("pyproject.toml",), ("requirements.lock",),
            ("https://pypi.org/simple",), ("pypi.org",), ("MIT",),
            DependencyResolutionBudget(5, 1_000_000, 2_000_000, 60),
            ".fam/envs/python", NOW,
            tuple(authority for authority in self.task.authorities if authority.value in {"modify", "network"}),
            ("example",),
        )
        policy = DependencyAdmissionPolicy(SpdxLicensePolicyAdapter())
        policy.authorize(request, self.task, self.grant, instant=NOW + timedelta(minutes=1))
        receipt = DependencyResolutionReceipt(
            "dependency-receipt-1", request.request_id, request.task_id,
            request.candidate_id, NOW, NOW + timedelta(seconds=1),
            DependencyResolutionStatus.ACCEPTED, ("a" * 64,), ("b" * 64,),
            ("c" * 64,), ("d" * 64,),
            (SbomComponent("pkg:pypi/example@1.0", "example", "1.0", "e" * 64, "MIT", True),),
            (), ("license-1",), ("pypi.org",), 1000, 2000,
            request.environment_path, ("f" * 64,), (),
        )
        policy.validate_receipt(request, receipt)
        with self.assertRaisesRegex(ValueError, "unapproved destination"):
            policy.validate_receipt(request, replace(receipt, network_destinations=("evil.example",)))

    def test_dependency_adapter_stages_artifacts_and_records_lock_sbom_and_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
            (root / "requirements.lock").write_text("")
            candidate = CandidateWorkspace(
                "candidate-1", "task-1", "baseline-1", "/owner", str(root),
                NOW, "full_copy_fallback", "a" * 64, (),
            )
            request = DependencyResolutionRequest(
                "dependency-1", "task-1", "candidate-1", "python3",
                ("pyproject.toml",), ("requirements.lock",),
                ("https://pypi.org/simple",), ("pypi.org",), ("MIT",),
                DependencyResolutionBudget(5, 1_000, 10_000, 60),
                ".fam/envs/python", NOW,
                tuple(authority for authority in self.task.authorities if authority.value in {"modify", "network"}),
                ("example",),
            )
            receipt = IsolatedDependencyResolverAdapter(
                FakeArtifactFetcher(), FakeCandidateInstaller(),
                FakeDependencyInspector(), clock=lambda: NOW,
            ).resolve(request, candidate)
            self.assertEqual(DependencyResolutionStatus.ACCEPTED, receipt.status)
            self.assertNotEqual(receipt.lockfile_before_sha256, receipt.lockfile_after_sha256)
            self.assertEqual(("pypi.org",), receipt.network_destinations)
            self.assertEqual("example", receipt.components[0].name)
            self.assertTrue(receipt.global_state_unchanged)
            self.assertTrue((root / ".fam/dependencies/dependency-1/example-1.0.whl").is_file())

    def test_admin_and_secret_powers_remain_separate_explicit_grants(self):
        change = HostAdministrationChangeSet(
            "host-change-1", "task-1", self.grant.grant_id, "owner-1",
            HostAdministrationMechanism.PACKAGE_MANAGER,
            ("https://packages.example/repository",), ("compiler=1.2.3",),
            ("install compiler 1.2.3 globally",), ("remove compiler 1.2.3",),
            ("host-before-1",), NOW, True, True, True,
            tuple(authority for authority in self.grant.authorities if authority.value in {"host_admin", "global_install"}),
        )
        broker = FakeHostBroker()
        receipt = EngineeringHostAdministrationService(
            HostAdministrationGate(FakeAuthenticator()), broker,
        ).apply(
            change, self.grant, "interactive-owner-auth",
            instant=NOW + timedelta(minutes=1),
        )
        self.assertEqual("external-root-broker", receipt.broker_id)
        self.assertEqual(1, len(broker.calls))
        direct = SecretUseAuthorization(
            "secret-use-1", "task-1", self.grant.grant_id, "owner-1",
            self.grant.principal_id, "secret.api",
            SecretUseLevel.DIRECT_MODEL_DISCLOSURE, "model-session-1",
            "Owner explicitly requests direct disclosure", NOW,
            NOW + timedelta(minutes=2), 1, "a" * 64,
        )
        direct_grant = replace(
            self.grant,
            secret_exposure=SecretExposurePolicy.DIRECT_MODEL_VISIBLE_DISCLOSURE,
        )
        SecretUseGate().authorize(
            direct, direct_grant, principal_id=self.grant.principal_id,
            consumer_id="model-session-1", instant=NOW + timedelta(minutes=1),
        )
        with self.assertRaises(ValueError):
            replace(direct, direct_disclosure_consequences_sha256=None)
        outcome = EngineeringSecretService(FakeSecretProvider()).use(
            direct, direct_grant, principal_id=self.grant.principal_id,
            consumer_id="model-session-1", instant=NOW + timedelta(minutes=1),
        )
        self.assertEqual("plaintext-secret", outcome.model_visible_value)
        self.assertNotIn("plaintext-secret", repr(outcome.receipt))

        opaque = replace(
            direct, authorization_id="secret-use-opaque",
            level=SecretUseLevel.OPAQUE_INJECTION,
            direct_disclosure_consequences_sha256=None,
            approved_consumer_id="tool-1",
        )
        service = EngineeringSecretService(FakeSecretProvider())
        opaque_outcome = service.use(
            opaque, self.grant, principal_id=self.grant.principal_id,
            consumer_id="tool-1", instant=NOW + timedelta(minutes=1),
        )
        self.assertIsNone(opaque_outcome.model_visible_value)
        with self.assertRaisesRegex(PermissionError, "consumed"):
            service.use(
                opaque, self.grant, principal_id=self.grant.principal_id,
                consumer_id="tool-1", instant=NOW + timedelta(minutes=1),
            )

    def test_passed_language_qualification_requires_positive_and_negative_receipts(self):
        with self.assertRaisesRegex(ValueError, "positive and negative"):
            LanguageToolQualification(
                "python-qualification", EngineeringEcosystem.PYTHON, "python3",
                "3.12", "positive", None, ToolQualificationStatus.PASSED, NOW,
            )

    def test_qualification_requires_real_positive_failure_and_containment_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory).resolve() / "positive"
            second = Path(directory).resolve() / "negative"
            first.mkdir()
            second.mkdir()
            base = dict(
                task_id="task-1", recipe_id="python-compile",
                recipe_payload_sha256=self.recipe.payload_sha256,
                sandbox_profile_id="sandbox-1", command_sha256="1" * 64,
                started_at=NOW, completed_at=NOW + timedelta(seconds=1),
                stdout_sha256="2" * 64, stderr_sha256="3" * 64,
                artifact_digests=(), network_destinations=(),
                isolation_evidence_ids=(
                    "bubblewrap-unshare-all", "cgroup-v2-systemd",
                    "bounded-rlimits",
                ),
            )
            from fam_os.core.engineering import EngineeringToolReceipt
            positive = EngineeringToolReceipt(
                receipt_id="positive", candidate_id="positive", exit_code=0,
                status=ToolQualificationStatus.PASSED, **base,
            )
            negative = EngineeringToolReceipt(
                receipt_id="negative", candidate_id="negative", exit_code=1,
                status=ToolQualificationStatus.FAILED, **base,
            )
            qualification = PolyglotQualificationService().qualify(
                "qualification-python", EngineeringEcosystem.PYTHON,
                "python3", "3.12", positive, negative, qualified_at=NOW,
                installed_release_id="release-1",
            )
            self.assertEqual(ToolQualificationStatus.PASSED, qualification.status)
            with self.assertRaisesRegex(ValueError, "negative"):
                PolyglotQualificationService().qualify(
                    "bad", EngineeringEcosystem.PYTHON, "python3", "3.12",
                    positive, replace(negative, status=ToolQualificationStatus.PASSED, exit_code=0),
                    qualified_at=NOW, installed_release_id="release-1",
                )


if __name__ == "__main__":
    unittest.main()
