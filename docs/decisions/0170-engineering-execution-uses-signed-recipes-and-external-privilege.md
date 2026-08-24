# ADR 0170: Engineering execution uses signed recipes and external privilege

Status: Accepted

## Context

FAM_OS needs broad polyglot build and test capability, optional owner-approved
raw shell, dependency installation, host administration, global installation,
and secret use. Treating those effects as one generic command channel would let
model output select executables, inherit credentials, widen network access, or
turn a permission to use a secret into permission to disclose it.

## Decision

The safe execution default is an Ed25519-signed `SignedToolRecipe`. Its signed
payload binds ecosystem, purpose, executable, complete argument template,
environment names, expected exits, verifier identities, network mode, and any
digest-checked read-only toolchain mounts. Core admits immutable recipe
coordinates only after digest and signature verification.

Recipe execution occurs in a transient candidate sandbox. Bubblewrap unshares
all namespaces, clears environment and capabilities, denies network by default,
binds only the candidate and signed toolchains, replaces `/home` and `/tmp`,
and disables host and repository Git configuration. A systemd user scope and
process rlimits bound memory, swap, CPU, processes, files, wall time, and output.
Receipts bind recipe, command, candidate, sandbox, exit, outputs, artifacts,
destinations, containment evidence, and bounded diagnostics.

Raw shell is separate. A single-use `RawShellAuthorization` binds the exact
command digest, shell, task, principal, workspace, environment, privilege tier,
issue/expiry, and an active break-glass `RAW_SHELL` grant. It never becomes a
model-held interactive session. Host-admin raw shell is forbidden; privileged
effects cross the `HostAdministrationBroker` port after interactive owner
authentication. Global installs additionally require `GLOBAL_INSTALL` and an
exact package source, predicted-effect, rollback, and before/after evidence
changeset.

Project dependency resolution is admitted separately against task and grant
registry, host, ecosystem, time, byte, package-count, license, vulnerability,
manifest, lockfile, isolated-environment, SBOM, and global-state postconditions.

Secret use has three non-interchangeable levels: opaque injection, redacted
transformation, and direct model disclosure. Direct disclosure requires the
grant's explicit direct-disclosure policy and a digest of the exact reviewed
consequences. Receipts contain output digests and redaction evidence, never the
secret value. One level cannot be inferred from another.

## Consequences

- Ordinary engineering does not require or expose a raw shell.
- Recipe tampering, unexpected exits, missing containment, unexpected network,
  and deliberately failing fixtures fail closed.
- Toolchains outside the base image are visible only at signed, digest-bound,
  read-only paths under `/opt/fam/toolchains` inside the sandbox.
- Core and models remain unprivileged; the operating system's normal
  authentication and privileged mechanisms stay behind an external broker.
- Source qualification is not installed-release qualification and must retain
  that label until the signed matrix passes.

## Alternatives considered

- Allow a model to emit arbitrary commands under ordinary execute authority:
  rejected because command text is authority-bearing.
- Put sudo or package-manager logic in Core: rejected because generative and
  unprivileged orchestration must not become the privilege boundary.
- Mount host home read-only for toolchains: rejected because it exposes
  unrelated owner data and credentials.
- Treat opaque secret use as disclosure permission: rejected because use and
  disclosure have different consequences.

## Evidence

- `src/fam_os/core/engineering/execution.py`
- `src/fam_os/core/engineering/execution_policy.py`
- `src/fam_os/core/engineering/dependencies.py`
- `src/fam_os/core/engineering/privileged.py`
- `src/fam_os/adapters/bubblewrap/engineering.py`
- `src/fam_os/adapters/linux/raw_shell.py`
- `tests/unit/test_engineering_execution.py`
- `tests/integration/test_polyglot_engineering_sandbox.py`
- `artifacts/engineering/phase27/polyglot-source-qualification-20260718-attempt2.json`

## Superseded decisions

None. This extends the existing verifier sandbox and ADRs 0165–0169 without
weakening authority, candidate-workspace, or truthful-assurance boundaries.
