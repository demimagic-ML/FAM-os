# ADR 0232: Repository manifests dominate engineering toolchain selection

Status: Accepted

## Context

Natural engineering previously added a verifier toolchain for every source-file
language observed anywhere inside the bounded repository scan. The selected
Node repository had two `package.json` manifests and one unrelated Python
utility. FAM therefore required both Node and Python test recipes. Node passed,
while Python correctly reported that it discovered no tests; the combined
policy rejected both the original candidate and its repair even though the
repository was not a Python project.

## Decision

Recognized repository manifests are authoritative for ordinary engineering
toolchain selection. When one or more supported manifests are present, FAM
deduplicates and selects only their ecosystems. File-language inference is a
fallback used only when no recognized manifest yields a toolchain.

This policy affects verifier selection, not filesystem authority. All observed
files remain bounded repository evidence, and a generated operation still must
pass candidate-plan validation and the exact changeset checkpoint.

## Consequences

- A utility or migration file no longer imposes an unrelated project-wide test
  suite.
- Manifested polyglot repositories continue to select all declared ecosystems.
- Manifest-less small repositories retain source-language fallback behavior.
- A future nested language subproject must provide its own recognized manifest
  or an explicit project-root selection before it becomes a required toolchain.

## Alternatives considered

- Accept `no tests ran` as a successful Python verification: rejected because
  that would misrepresent absence of verification as proof.
- Keep every observed language and repair indefinitely: rejected because no
  code repair can create an absent, unrelated project test suite reliably.
- Ask the model which verifier to run: rejected because verifier selection is
  trusted deterministic policy, not model output.

## Evidence

- `src/fam_os/product/natural_engineering_api.py`
- `tests/unit/test_product_natural_engineering_api.py`
- `artifacts/product/phase30/natural-plan-followup-acceptance-20260719-01/evidence.json`
