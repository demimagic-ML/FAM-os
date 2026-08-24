# ADR 0167: Owner authentication admits engineering grants

Status: Accepted

## Context

Typed authorities and expert advisory scopes do not establish who may activate
a machine-effect grant. FAM_OS needs owner-selectable power, immediate
revocation, exceptional full authority, and optional verification waiver while
ensuring that untrusted text or tool data cannot mint authority or elevate an
assurance claim.

## Decision

Delegation modes expand deterministically into visible individual
`EngineeringAuthority` values. Safe default, workspace operator, engineering
administrator, custom, and full-owner modes are named profiles, not hidden
master booleans. Presets reject overrides; custom mode records its exact list;
full-owner mode expands to the complete public enum.

An `EngineeringAuthorityGrant` binds owner and principal to purpose, expiry,
one action/changeset/task/session target, workspace and path limits,
toolchains, network hosts, registries, Git targets, named secrets, resource
impact, reversibility, secret exposure, verification requirement, inheritance,
and lifecycle state. Inheritance defaults off and is forbidden for high-risk
grants.

Core admits a grant only through an `OwnerAuthorityVerifier` trusted port. The
verifier checks an authenticated approval bound to the canonical grant digest.
Prompt text, repository content, model candidates, and tool output may contain
identical-looking contract data but cannot make that port return true. The
component ledger denies unadmitted, expired, revoked, consumed, principal-
mismatched, target-mismatched, path-denied, resource-exceeding, and authority-
missing requests.

Raw shell, host administration, global installation, production mutation,
policy change, protected-ref writes, self-update, and verification waiver
require a separate authenticated break-glass decision. Its exact consequence
digest, authority tuple, verification policy, target kind, target ID, owner,
grant, and expiry must match. Approval may cover exactly one action, one
changeset, one task, or one bounded session.

Execution assurance is independent of authority. Only passing trusted verifier
evidence produces `verified`. An applied effect without passing evidence is
`executed_unverified`; an explicit waiver decision produces
`verification_waived`. No owner power, including policy-change or full-owner
delegation, can relabel either state as verified.

## Consequences

- The owner can deliberately grant every defined power while keeping scope and
  consequences inspectable.
- Model or tool control of a serialized grant is insufficient for admission.
- Revocation and expiry deny subsequent authorizations immediately in the
  component lifecycle; action and changeset grants can be consumed once.
- Production persistence, restart reconciliation, authentication adapters, and
  effect providers remain later work and cannot be claimed from the in-memory
  fake-driven ledger.
- Assurance displays remain truthful even when the owner waives verification.

## Alternatives considered

- A permanent safety ban on administrator or production power: rejected because
  the owner is the final authority over the machine.
- A single unrestricted-access switch: rejected because it hides capabilities,
  scope, resource impact, and revocation consequences.
- Treat a confirmation phrase in the prompt as owner authentication: rejected
  because models and repository instructions can reproduce phrases.
- Let full-owner authority imply verified output: rejected because permission
  and evidence answer different questions.

## Evidence

- `src/fam_os/core/engineering/delegation.py`
- `src/fam_os/core/engineering/grants.py`
- `src/fam_os/core/engineering/break_glass.py`
- `src/fam_os/core/engineering/grant_policy.py`
- `src/fam_os/core/engineering/assurance.py`
- `tests/unit/test_engineering_grant_lifecycle.py`
- `tests/unit/test_shell_engineering_projection.py`

## Superseded decisions

None. This completes the component-level admission policy introduced by ADR
0165 and preserves the advice/effect distinction from ADR 0166.
