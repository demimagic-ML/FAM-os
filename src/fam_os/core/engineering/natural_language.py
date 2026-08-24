"""Compile natural-language engineering intent into an exact owner proposal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import re

from fam_os.core.agent import AgentAuthorityProfile

from fam_os.core.engineering.authority import (
    CheckpointPolicy,
    EngineeringAuthority,
    EngineeringOperation,
    EngineeringTaskEnvelope,
)
from fam_os.core.engineering.delegation import EngineeringDelegationMode
from fam_os.core.engineering.grant_policy import engineering_grant_digest
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    EngineeringGrantScope,
    EngineeringGrantScopeKind,
    EngineeringResourceImpact,
    GrantLifecycleState,
    ReversibilityPolicy,
    SecretExposurePolicy,
    VerificationRequirement,
)
from fam_os.core.engineering.master_loop import EngineeringLoopBudget
from fam_os.core.engineering.natural_integration_resources import (
    INTEGRATION_RESOURCE_AUTHORITIES,
    build_natural_integration_resource_grant,
    natural_integration_resource_grant_id,
)
from fam_os.core.engineering.task_definition import (
    EngineeringTaskDefinition,
    engineering_task_digest,
)


_MUTATION = re.compile(
    r"\b(create|add|write|edit|modify|change|replace|transform|implement|fix|"
    r"repair|refactor|migrate|redesign|generate|delete|remove|move|rename|update)\b",
)
_EXECUTION = re.compile(
    r"\b(run|execute|build|test|tests|lint|type[- ]?check|compile|profil(?:e|ing)|"
    r"debug|trace|tracing|backtrace|dump|race|leak|benchmark|performance)\b",
)
_DELETE = re.compile(r"\b(delete|remove)\b")
_MOVE = re.compile(r"\b(move|rename)\b")
_DEPENDENCY = re.compile(r"\b(dependency|dependencies|package|packages)\b")
_DESIGN = re.compile(r"\b(design|ui|ux|asset|image|icon|svg|css)\b")
_DATABASE = re.compile(r"\b(database|sqlite|schema migration|migration|migrate)\b")
_INTEGRATION_ENVIRONMENT = re.compile(
    r"\b(integration environment|end[- ]to[- ]end|e2e|browser preview|"
    r"preview (?:the )?(?:site|web app|page)|serve (?:the )?"
    r"(?:site|web app|page)|run (?:the )?(?:site|web app)|"
    r"(?:postgresql|postgres) (?:service|container)|"
    r"(?:run|start|launch|test) (?:a |the )?(?:postgresql|postgres)"
    r"(?: (?:service|container|database))?)\b",
)
_HIGH_RISK = (
    (EngineeringAuthority.NETWORK, re.compile(r"\b(fetch|download|network|internet|registry)\b")),
    (EngineeringAuthority.PUBLISH, re.compile(r"\b(push|publish|pull request|merge request|deploy)\b")),
    (EngineeringAuthority.RAW_SHELL, re.compile(r"\b(raw shell|shell command|terminal command)\b")),
    (EngineeringAuthority.HOST_ADMIN, re.compile(r"\b(sudo|root|host-wide|systemd)\b")),
    (EngineeringAuthority.SECRET_USE, re.compile(r"\b(secret|credential|password|api key|token)\b")),
    (EngineeringAuthority.PRODUCTION_MUTATE, re.compile(r"\b(production|prod environment)\b")),
)


@dataclass(frozen=True, slots=True)
class NaturalLanguageEngineeringProposal:
    proposal_id: str
    prompt_sha256: str
    grant: EngineeringAuthorityGrant
    definition: EngineeringTaskDefinition
    budget: EngineeringLoopBudget
    separately_confirmed_authorities: tuple[EngineeringAuthority, ...]
    integration_resource_grant: EngineeringAuthorityGrant | None = None

    def __post_init__(self) -> None:
        if not self.proposal_id.strip() or len(self.prompt_sha256) != 64:
            raise ValueError("natural-language engineering proposal identity is invalid")
        int(self.prompt_sha256, 16)
        task = self.definition.task
        if (
            task.grant_id != self.grant.grant_id
            or task.owner_id != self.grant.owner_id
            or task.task_id != self.grant.scope.scope_id
            or task.workspace_roots != self.grant.scope.workspace_roots
            or not set(task.authorities).issubset(self.grant.authorities)
        ):
            raise ValueError("natural-language engineering proposal scope is inconsistent")
        resource_grant = self.integration_resource_grant
        if resource_grant is not None:
            resource_authorities = tuple(
                item for item in resource_grant.authorities
                if item is not EngineeringAuthority.EXECUTE
            )
            expected = tuple(
                item for item in self.separately_confirmed_authorities
                if item in INTEGRATION_RESOURCE_AUTHORITIES
            )
            if (
                resource_authorities != expected
                or resource_grant.grant_id
                != natural_integration_resource_grant_id(self.grant.grant_id)
                or resource_grant.owner_id != self.grant.owner_id
                or resource_grant.principal_id != self.grant.principal_id
                or resource_grant.scope.kind is not EngineeringGrantScopeKind.TASK
                or resource_grant.scope.scope_id != task.task_id
                or resource_grant.scope.workspace_roots != task.workspace_roots
                or resource_grant.scope.toolchains != ("integration-environment",)
            ):
                raise ValueError(
                    "natural integration resource grant is not exact"
                )


class NaturalLanguageEngineeringPlanner:
    """Interpret words as a proposal; never authenticate or activate authority."""

    def propose(
        self, *, prompt: str, workspace_root: str, owner_id: str,
        principal_id: str, task_id: str, grant_id: str,
        toolchains: tuple[str, ...], now: datetime,
        task_intent: str | None = None,
        authority_profile: AgentAuthorityProfile = AgentAuthorityProfile.WORKSPACE,
        git_available: bool = True,
    ) -> NaturalLanguageEngineeringProposal:
        normalized = " ".join(prompt.casefold().split())
        if not normalized or len(prompt.encode("utf-8")) > 16_384:
            raise ValueError("engineering prompt is empty or exceeds its bound")
        resolved_intent = prompt if task_intent is None else task_intent
        if not resolved_intent.strip() or len(resolved_intent.encode("utf-8")) > 32_768:
            raise ValueError("resolved engineering intent is empty or exceeds its bound")
        high_risk = tuple(
            authority for authority, pattern in _HIGH_RISK
            if pattern.search(normalized)
        )
        authorities, operations = _ordinary_scope(
            normalized, git_available=git_available,
        )
        if authority_profile is AgentAuthorityProfile.ASK:
            authorities = (
                EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
            )
            operations = (EngineeringOperation.READ,)
            high_risk = ()
        elif authority_profile is AgentAuthorityProfile.FULL_OS:
            full_os_authorities = set((
                *authorities, EngineeringAuthority.NETWORK,
                EngineeringAuthority.RAW_SHELL, EngineeringAuthority.HOST_ADMIN,
            ))
            authorities = tuple(
                item for item in EngineeringAuthority
                if item in full_os_authorities
            )
            high_risk = tuple(
                item for item in high_risk
                if item not in {
                    EngineeringAuthority.RAW_SHELL,
                    EngineeringAuthority.HOST_ADMIN,
                    EngineeringAuthority.NETWORK,
                }
            )
        expires = now + timedelta(hours=2)
        impact = EngineeringResourceImpact(7_200, 64, 128, 512, 64 * 1024**2, 0)
        integration_toolchains = (
            ("integration-environment",)
            if natural_integration_environment_requested(normalized) else ()
        )
        scoped_toolchains = tuple(dict.fromkeys((
            *toolchains, *integration_toolchains,
        )))
        scope = EngineeringGrantScope(
            EngineeringGrantScopeKind.TASK, task_id, (workspace_root,), (),
            (".git/**", ".fam/**"), scoped_toolchains, (), (), (), (), (),
        )
        grant = EngineeringAuthorityGrant(
            grant_id, owner_id, principal_id, EngineeringDelegationMode.CUSTOM,
            authorities, scope, prompt, now, expires, GrantLifecycleState.ACTIVE,
            ReversibilityPolicy.REQUIRED, SecretExposurePolicy.NONE,
            VerificationRequirement.REQUIRED, impact,
            break_glass_decision_id=(
                f"break-glass-decision-{grant_id}"
                if authority_profile is AgentAuthorityProfile.FULL_OS else None
            ),
        )
        task = EngineeringTaskEnvelope(
            task_id, owner_id, grant_id, resolved_intent, now, expires, (workspace_root,),
            authorities, operations, (), (".git/**", ".fam/**"), toolchains,
            (), (), impact.max_wall_seconds, impact.max_tool_runs,
            impact.max_changed_files, impact.max_changed_bytes,
            None, None, CheckpointPolicy.EVERY_CHANGESET,
        )
        definition = EngineeringTaskDefinition(
            f"definition-{task_id}", task, "acceptance.engineering.required",
            now, engineering_task_digest(task),
        )
        budget = EngineeringLoopBudget(
            131_072, impact.max_wall_seconds, impact.max_tool_runs, 0,
            impact.max_changed_files, impact.max_changed_bytes,
        )
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        resource_grant = (
            build_natural_integration_resource_grant(
                prompt, grant, task, high_risk, now, expires,
            )
            if natural_integration_environment_requested(prompt) else None
        )
        proposal = NaturalLanguageEngineeringProposal(
            f"proposal-{task_id}", digest, grant, definition, budget, high_risk,
            resource_grant,
        )
        # Compute now so activation callers have one canonical consequence digest.
        engineering_grant_digest(proposal.grant)
        return proposal


def _ordinary_scope(
    normalized: str, *, git_available: bool,
) -> tuple[tuple[EngineeringAuthority, ...], tuple[EngineeringOperation, ...]]:
    mutation = _MUTATION.search(normalized) is not None
    execution = mutation or _EXECUTION.search(normalized) is not None
    authorities = [EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE]
    operations = [EngineeringOperation.READ]
    if mutation:
        authorities.append(EngineeringAuthority.MODIFY)
        operations.extend((EngineeringOperation.CREATE, EngineeringOperation.REPLACE))
        if _DELETE.search(normalized):
            operations.append(EngineeringOperation.DELETE)
        if _MOVE.search(normalized):
            operations.append(EngineeringOperation.MOVE)
        if _DEPENDENCY.search(normalized):
            operations.append(EngineeringOperation.MANAGE_DEPENDENCY)
        if _DESIGN.search(normalized):
            operations.append(EngineeringOperation.MANAGE_DESIGN)
        if git_available:
            # A valid repository receives reversible local Git delivery. Plain
            # folders retain the candidate preview, approval, apply and rollback
            # workflow without pretending that Git exists.
            operations.append(EngineeringOperation.GIT_WRITE)
    if execution:
        authorities.append(EngineeringAuthority.EXECUTE)
        operations.append(EngineeringOperation.RUN_TOOL)
    return tuple(authorities), tuple(dict.fromkeys(operations))


def natural_integration_environment_requested(intent: str) -> bool:
    normalized = " ".join(intent.casefold().split())
    return _INTEGRATION_ENVIRONMENT.search(normalized) is not None
