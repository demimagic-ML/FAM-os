# ADR 0189: Retained integration artifacts are post-stop content evidence

Status: Accepted

## Context

Integration plans and receipts already declare retained artifact paths and
digests, but concrete adapters rejected them. Treating retention as an
unbounded directory copy would create a new filesystem authority, allow
symlink escapes, and make results race with still-running services.

## Decision

An integration environment may retain only explicitly declared
candidate-relative regular files. Cleanup or reconciliation first stops the
recorded runtime resources, then opens each file with no-follow semantics,
checks every path component for symlinks and confinement, and hashes through a
bounded descriptor. Device, inode, size, and modification time must remain
stable across hashing. Aggregate bytes must fit the plan's existing
`max_changed_bytes` budget.

The adapter does not copy or relocate retained files. It emits ordered
`IntegrationRetainedArtifact` values containing the declared relative path and
SHA-256 in the terminal cleanup receipt. Candidate-local `.fam/integration`
state is never eligible for retention. Missing, unsafe, oversized, or changing
artifacts fail closed and leave durable reconciliation available; stopped
runtime authority is not restarted.

For Docker, a volume marked `retain_artifacts` must name a candidate path also
present in the plan's retained artifact list. This does not change current
volume semantics or make an undeclared tmpfs persistent.

## Consequences

- Verification and owner surfaces receive content-bound evidence without a new
  artifact store or implicit filesystem write.
- Hashes describe quiescent files because runtime shutdown precedes capture.
- Large artifacts consume the already admitted changed-byte budget.
- Durable artifact storage, export, garbage collection, and disclosure policy
  remain separate capabilities.

## Evidence

- `src/fam_os/adapters/integration/retained_artifacts.py`
- `src/fam_os/adapters/integration/process_environment.py`
- `src/fam_os/adapters/integration/docker_environment.py`
- `tests/unit/test_integration_retained_artifacts.py`
- `tests/integration/test_process_api_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt6.json`
