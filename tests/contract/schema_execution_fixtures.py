"""Representative polyglot execution, dependency, and privileged documents."""

import base64
from datetime import timedelta

from fam_os.core.engineering import (
    DependencyResolutionBudget, DependencyResolutionReceipt,
    DependencyResolutionRequest, DependencyResolutionStatus,
    EngineeringAuthority, EngineeringEcosystem, EngineeringSandboxProfile,
    EngineeringToolReceipt, HostAdministrationChangeSet,
    HostAdministrationMechanism, HostAdministrationReceipt, HostChangeStatus,
    LanguageToolQualification, PolyglotRecipeMatrix, RawShellAuthorization,
    RawShellPrivilegeTier, SandboxNetworkMode, SbomComponent,
    SecretUseAuthorization, SecretUseLevel, SecretUseReceipt, SignedToolRecipe,
    ToolQualificationStatus, ToolRecipePurpose,
)
from fam_os.core.engineering.recipe_matrix import REQUIRED_PURPOSES
from tests.contract.schema_engineering_fixtures import NOW


SIGNATURE = base64.b64encode(b"\0" * 64).decode()


def recipe(ecosystem, purpose, suffix=""):
    return SignedToolRecipe(
        f"{ecosystem.value}-{purpose.value}{suffix}", "1.0.0", ecosystem,
        purpose, "/usr/bin/tool", ("--check", "{workspace}"), ("PATH",),
        (0,), (f"verifier.{ecosystem.value}.{purpose.value}",),
        "tool-recipe-key", "a" * 64, SIGNATURE,
    )


def execution_schema_values() -> tuple[object, ...]:
    recipes = tuple(
        recipe(ecosystem, purpose)
        for ecosystem, purposes in REQUIRED_PURPOSES.items()
        for purpose in sorted(purposes, key=lambda item: item.value)
    )
    acceptance = recipe(EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE)
    integrity = recipe(
        EngineeringEcosystem.PYTHON, ToolRecipePurpose.STATIC_ANALYSIS,
        "-package-integrity",
    )
    recipes = (*recipes, acceptance, integrity)
    qualifications = tuple(
        LanguageToolQualification(
            f"qualification-{ecosystem.value}", ecosystem,
            f"{ecosystem.value}-tool", "1.0", f"positive-{ecosystem.value}",
            f"negative-{ecosystem.value}", ToolQualificationStatus.PASSED, NOW,
            "release-1",
        )
        for ecosystem in EngineeringEcosystem
    )
    matrix = PolyglotRecipeMatrix(
        "polyglot-matrix-1", recipes, qualifications,
        (acceptance.recipe_id,), (integrity.recipe_id,),
    )
    profile = EngineeringSandboxProfile(
        "sandbox-profile-1", 256 * 1024**2, 2, 30, 16, 65_536,
        8 * 1024**2, SandboxNetworkMode.DENIED, (),
        (("PATH", "/usr/bin:/bin"), ("LANG", "C.UTF-8")),
    )
    raw_shell = RawShellAuthorization(
        "raw-shell-1", "grant-engineering-1", "task-1", "fam-core",
        "/workspace", "/usr/bin/bash", "b" * 64,
        (("PATH", "/usr/bin:/bin"),), RawShellPrivilegeTier.HOST_USER,
        NOW, NOW + timedelta(minutes=5),
    )
    tool_receipt = EngineeringToolReceipt(
        "engineering-tool-receipt-1", "task-1", "candidate-1",
        recipes[0].recipe_id, recipes[0].payload_sha256, profile.profile_id,
        "c" * 64, NOW, NOW + timedelta(seconds=1), 0, "d" * 64,
        "e" * 64, ("f" * 64,), (), ("bubblewrap", "cgroup"),
        ToolQualificationStatus.PASSED,
    )
    dependency_request = DependencyResolutionRequest(
        "dependency-request-1", "task-1", "candidate-1", "python",
        ("pyproject.toml",), ("requirements.lock",),
        ("https://pypi.org/simple",), ("pypi.org",), ("MIT",),
        DependencyResolutionBudget(10, 1_000_000, 2_000_000, 60),
        ".fam/envs/python", NOW,
        (EngineeringAuthority.MODIFY, EngineeringAuthority.NETWORK),
        ("example",),
    )
    dependency_receipt = DependencyResolutionReceipt(
        "dependency-receipt-1", dependency_request.request_id, "task-1",
        "candidate-1", NOW, NOW + timedelta(seconds=2),
        DependencyResolutionStatus.ACCEPTED, ("1" * 64,), ("2" * 64,),
        ("3" * 64,), ("4" * 64,),
        (SbomComponent("pkg:pypi/example@1", "example", "1", "5" * 64, "MIT", True),),
        (), ("license-1",), ("pypi.org",), 100, 200,
        dependency_request.environment_path, ("6" * 64,), (),
    )
    host_change = HostAdministrationChangeSet(
        "host-change-1", "task-1", "grant-engineering-1", "owner-1",
        HostAdministrationMechanism.SYSTEMD, (), (),
        ("restart bounded service",), ("restart previous service",),
        ("host-before-1",), NOW,
    )
    host_receipt = HostAdministrationReceipt(
        "host-receipt-1", host_change.change_set_id, "broker-1",
        "owner-auth-1", HostChangeStatus.APPLIED, NOW,
        NOW + timedelta(seconds=1), ("host-before-1",), ("host-after-1",),
        ("service restarted",), (), 0, "7" * 64,
    )
    secret_auth = SecretUseAuthorization(
        "secret-auth-1", "task-1", "grant-engineering-1", "owner-1",
        "fam-core", "secret.api", SecretUseLevel.REDACTED_TRANSFORMATION,
        "tool-1", "redacted API operation", NOW, NOW + timedelta(minutes=5), 1,
    )
    secret_receipt = SecretUseReceipt(
        "secret-receipt-1", secret_auth.authorization_id, "secret.api",
        "tool-1", secret_auth.level, NOW, "8" * 64, "redaction-1",
    )
    return (
        recipes[0], profile, raw_shell, tool_receipt, qualifications[0], matrix,
        dependency_request, dependency_receipt, host_change, host_receipt,
        secret_auth, secret_receipt,
    )
