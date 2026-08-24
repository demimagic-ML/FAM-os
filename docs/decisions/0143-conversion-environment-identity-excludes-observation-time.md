# ADR 0143: Conversion environment identity excludes observation time

Status: Accepted

## Context

Conversion approval binds an exact llama.cpp source revision, conversion-script
digests, offline wheelhouse, Python executable, package versions, and Ollama
version. The backend probes those facts again immediately before consuming the
approval. The first physical release attempt proved that the manifest also
included `observed_at`; two observations of unchanged software therefore had
different digests and every real conversion necessarily failed closed.

## Decision

`observed_at` remains required provenance on each
`FactoryConversionEnvironment`, but it is excluded from
`manifest_sha256`. Environment identity contains only the immutable executable,
source, dependency, and runtime-version facts that conversion approval intends
to pin. Any change to those facts still changes the manifest and denies the
approved conversion.

Physical release-attempt identity also scopes conversion approvals, one-use
conversion IDs, runtime model references, package versions, canaries, rollback,
and retirement requests. A failed attempt is preserved and a retry cannot reuse
its authority or collide with a partially installed qualification package.

## Consequences

- Re-probing an unchanged conversion environment yields the same identity.
- Observation timestamps remain stored for audit and freshness reasoning.
- Source, script, wheel, interpreter, package, or Ollama changes still fail the
  pre-consumption comparison.
- Release qualification retries create new one-use authority and artifact
  identities rather than mutating failed attempts.

## Alternatives considered

- Reusing the first probe object without a second observation was rejected
  because it would remove the pre-execution tamper check.
- Ignoring the mismatch in the backend was rejected because it would weaken an
  approval boundary.
- Freezing the clock was rejected because a test-only time workaround would not
  make production environment identity correct.

## Evidence

- `src/fam_os/expert_factory/conversion.py`
- `src/fam_os/adapters/training/llama_cpp_conversion_backend.py`
- `tools/phase22_release_exit/scenario.py`
- `tests/unit/test_factory_conversion.py`
