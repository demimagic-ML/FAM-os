# ADR 0057: Bind reference packages to external runtime artifacts

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The reference Ollama models already occupy tens of gigabytes. Copying them into
a second FAM-owned package directory would waste SSD capacity and would imply
that package removal owns the user's model download. Model names alone are not
immutable identities. The local artifacts also have no FAM package signatures.

## Decision

Add strict expert runtime bindings and an observed runtime-artifact catalog.
Bind each package to the full digest returned for one exact installed Ollama
model. Install an external artifact reference through the normal lifecycle
without copying bytes. Re-observe its digest for idempotent install and rollback.
Never delete the downloaded model when FAM package state is removed.

Admit this workstation set only under a named development policy that explicitly
allows `local_unverified`; do not label third-party models built-in or signed.
Keep Laguna and Gemma at escalation tier. Retain complete 1.0.1 manifests and
bindings beside current 1.0.2 definitions so rollback restores a resolvable,
policy-admissible package.

Require package-aware benchmarks to prove enabled lifecycle state, exact
binding/digest, declared capability/tier selection, runtime-adapter execution,
strict verification, and full resource evidence.

## Consequences

- FAM avoids duplicating approximately 41 GB for Laguna and Gemma.
- Updating an Ollama tag to different bytes fails package verification.
- Removing package metadata cannot unexpectedly remove a user model.
- Development trust remains visibly weaker than signed distribution trust.
- Rollback retains definitions as well as model bytes.
- Exact model inventory and license changes require a new package version.
- The schema catalog increases to 51 strict roots.

## Alternatives considered

1. Copy Ollama blobs: rejected for storage waste, private layout coupling, and
   ambiguous deletion ownership.
2. Trust only the model tag: rejected because tags can move.
3. Mark local models built-in: rejected because FAM did not build or anchor them.
4. Generate and store a development private signing key: rejected because the
   repository must not contain signing secrets.
5. Keep only current definitions: rejected because artifact-only rollback is not
   a complete resolvable package rollback.

## Evidence

- `src/fam_os/experts/runtime_binding.py`
- `src/fam_os/experts/installed_candidates.py`
- `src/fam_os/adapters/ollama/model_catalog.py`
- `src/fam_os/adapters/ollama/artifact_store.py`
- `configs/packages/`
- `artifacts/expert_fabric/phase6/`
- `artifacts/workstation/20260716T170632701276Z/`
