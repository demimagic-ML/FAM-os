# ADR 0160: Signed expert archives require canonical members and exact verifiers

Status: Accepted

## Context

A signature authenticates archive bytes, but duplicate or non-canonical member
names can still make extraction depend on member order. Runtime expert scopes
also previously proved only that required verifiers were present, allowing an
undeclared extra verifier to alter a scope's authority.

## Decision

Signed expert archives reject duplicate member paths, absolute paths, parent
traversal, and member names whose canonical representation differs from the
signed name. Provider manifests and the runtime catalog use strict JSON.

Each runtime expert scope must name exactly the verifier set declared by the
selected signed expert manifest. A subset or superset is invalid. Reference
packages no longer declare a verifier that does not exist in the signed
verifier catalog.

## Consequences

- Archive interpretation cannot be changed by duplicate-member ordering.
- Runtime verifier authority is reconstructed exactly from signed packages.
- A verifier addition or removal requires an explicit package and catalog
  change rather than silently broadening an existing scope.
- Previously tolerated ambiguous or over-declared packages fail closed.

## Alternatives considered

- Accept the final duplicate archive member: rejected because signed bytes do
  not define which extraction implementation is authoritative.
- Require only a verifier subset: rejected because it permits undeclared
  verification policy to influence routing and result release.

## Evidence

- `src/fam_os/core/production/model_catalog_archive.py`
- `src/fam_os/core/production/model_catalog_scopes.py`
- `tests/unit/test_packaged_runtime_catalog.py`
- `tests/integration/test_reference_expert_package_definitions.py`
- `handoffs/0183-canonical-expert-archives-and-exact-verifiers.md`

