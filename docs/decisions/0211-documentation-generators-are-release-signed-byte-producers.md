# ADR 0211: Documentation generators are release-signed byte producers

Status: Accepted

## Context

ADR 0210 added trusted admission and stale-output blocking, but no installed
producer could create an admissible receipt. Reusing a shell recipe would imply
raw command execution and would give the generator direct candidate authority.
A model-selected coordinate would also let untrusted output influence the
trusted implementation choice.

## Decision

FAM_OS has a distinct `SignedDocumentationRecipe` contract. Each recipe binds
one artifact kind, deterministic generator adapter, output media type, source
and output bounds, release signer, payload digest, and Ed25519 signature. The
release assembler ships recipes for diagrams, API references, runbooks,
changelogs, and generated-code manifests in the expert archive. Installed
composition admits them only after verifying the release manifest, release
signer, member safety, recipe payload, and recipe signature.

Core policy derives required artifact kinds from admitted natural intent and
selects only an installed recipe. The exact generation request is persisted
before any candidate effect. The adapter returns bounded UTF-8 bytes and never
receives filesystem or shell authority. Core converts those bytes plus
ownership and regeneration content into ordinary typed candidate edits under
the active task grant, then independently re-hashes and admits the receipt from
the candidate filesystem.

If the active release lacks the required catalog, a relevant task fails
truthfully. The generated files enter the same verification, changeset,
transactional apply, local commit, and rollback path as model-proposed files.
Git delivery stages file-bearing effects; directory-only candidate operations
remain in the filesystem transaction but are not claimed as Git paths.
Directory moves fail closed until file-expanded delivery evidence exists.

## Consequences

- Models and clients cannot choose recipe coordinates or issue trusted
  generation receipts.
- Generator adapters cannot mutate the candidate directly or obtain terminal
  authority.
- Interrupted work has durable request intent before any generated file
  appears and can resume through idempotent candidate edits.
- All five recipe kinds ship in the signed installed artifact.
- Phase 30.6 remains open for automatic stale regeneration, governance-file
  digest binding, complete generated traceability, live production-verifier
  proof, and the final scenario matrix.

## Alternatives considered

- Reuse `SignedToolRecipe` and execute a generator command. Rejected because a
  deterministic byte producer does not need process authority and command
  semantics would broaden the boundary.
- Let the model name a generator. Rejected because installed implementation
  selection is trusted policy.
- Write output directly from the adapter. Rejected because all candidate
  effects must pass the existing grant, budget, recovery, preview, and rollback
  services.
- Treat explicit directories as staged Git paths. Rejected because Git tracks
  file effects, not empty directory entries.

## Evidence

- `src/fam_os/core/engineering/documentation_recipes.py`
- `src/fam_os/core/engineering/documentation_policy.py`
- `src/fam_os/adapters/documentation/deterministic.py`
- `src/fam_os/product/natural_engineering_documentation.py`
- `src/fam_os/product/composition/documentation_recipes.py`
- `src/fam_os/product/release_assembly.py`
- `tests/unit/test_documentation_recipes.py`
- `tests/integration/test_natural_engineering_checkpoint.py`
- `artifacts/product/phase30/governed-documentation-install-20260719-01/evidence.json`

## Superseded decisions

None. This supplies the trusted producer anticipated by ADR 0210.
