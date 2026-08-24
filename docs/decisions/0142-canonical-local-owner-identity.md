# ADR 0142: Local owner identity is the canonical decimal Unix UID

Status: Accepted

## Context

The installed product stores owner-scoped records under the decimal Unix UID,
for example `1000`. Early Phase 22 physical tools independently constructed
`uid:1000`. Both strings referred to the same operating-system account, but
owner-encrypted repositories correctly treated them as different principals.
A promotable signed evaluation therefore existed in the physical database but
was unavailable to the real release service.

## Decision

All local product composition roots and physical factory tools derive durable
owner identity through `local_owner_id(uid)`. Its canonical representation is
the base-10 Unix UID with no prefix. Invalid, Boolean, and negative values fail
before repository composition.

Previously signed Phase 22 evidence is not copied, migrated, or rebound. The
physical training and evaluation checkpoint is repeated under the canonical
owner so conversion consumes the exact decision written by the product
repositories.

## Consequences

- One local account has one stable owner namespace across Shell, storage,
  application, peer, training, evaluation, conversion, and release services.
- Repository scope checks remain strict string comparisons; no alias weakens
  the authorization boundary.
- Historical `uid:<number>` experiment databases remain immutable diagnostic
  evidence and cannot authorize release.
- New local-owner call sites use the shared constructor rather than formatting
  identifiers independently.

## Alternatives considered

- Copying the signed decision into the installed namespace was rejected because
  it would break the signer, repository, and owner provenance chain.
- Accepting both strings as aliases was rejected because ambiguous principal
  aliases weaken encrypted repository isolation.
- Changing the installed product to `uid:<number>` was rejected because it
  would strand all existing owner-scoped product state.

## Evidence

- `src/fam_os/product/owner_identity.py`
- `src/fam_os/product/composition/storage_unit.py`
- `tools/phase22_specialist_exit/scenario.py`
- `tests/unit/test_owner_identity.py`
