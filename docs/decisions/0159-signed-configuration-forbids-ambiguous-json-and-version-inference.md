# ADR 0159: Signed configuration forbids ambiguous JSON and version inference

Status: Accepted

## Context

The signed expert archive may contain side-by-side package versions. Runtime
composition previously selected one by comparing `package_version` strings.
The package contract does not require SemVer, so no generic string ordering can
define "latest" correctly; even dotted numeric versions misorder `1.0.10` and
`1.0.2` lexically.

Python's default JSON decoder also accepts duplicate object keys and keeps the
last occurrence. A signed or local configuration could therefore have two
different textual authorities while validation observed only one.

## Decision

Each signed runtime `expert_scopes` entry names the exact `package_id`,
`package_version`, and `expert_id` coordinate it activates. Runtime composition
requires the exact manifest and runtime binding for that coordinate and never
infers a newest version. Other signed versions may remain in the archive for
registry, rollback, or migration use, but they are inactive until the signed
runtime catalog explicitly selects them.

The contract JSON decoder rejects duplicate keys at every object depth and
continues to reject non-finite constants. The untyped runtime model catalog uses
the same strict rules before interpreting any model, scope, verifier, or package
field. Duplicate manifests and bindings at one exact coordinate also fail
composition.

## Consequences

- Package activation is deterministic for arbitrary version identifiers.
- Adding a side-by-side version cannot silently change live routing.
- Promoting a version requires a visible signed catalog change.
- Textually ambiguous JSON fails before schema or domain decoding.
- Existing canonical documents remain byte-compatible; malformed documents
  that relied on duplicate-key last-write behavior are rejected.

## Alternatives considered

- Parse every package version as SemVer: rejected because the public package
  contract never imposed SemVer and this would retroactively narrow it.
- Natural-sort numeric segments: rejected because prerelease and vendor version
  semantics would remain undefined.
- Keep last-key-wins JSON behavior because releases are signed: rejected because
  signatures prove bytes, not unambiguous interpretation.
- Select the first archive member: rejected because tar member order is not
  package authority.

## Evidence

- `src/fam_os/core/production/model_catalog.py`
- `src/fam_os/schemas/codec.py`
- `configs/packages/runtime/model-catalog.json`
- `tests/unit/test_packaged_runtime_catalog.py`
- `tests/contract/test_schema_roundtrip.py`
- `tests/integration/test_reference_expert_package_definitions.py`

