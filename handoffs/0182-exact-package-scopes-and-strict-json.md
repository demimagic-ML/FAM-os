# Handoff 0182: Exact package scopes and strict JSON

**Date:** 2026-07-18  
**Plan step:** Whole-Master-Plan corrective audit, Phases 2, 6, and 18  
**Status:** Source implementation and focused qualification complete  
**Previous handoff:** `0181-verifier-compatible-expert-scoped-runtime-routing.md`

## Objective

Continue the signed catalog blast-radius audit and remove two sources of
ambiguous authority: inferred package-version ordering and duplicate JSON keys.

## Defects confirmed

- Runtime composition compared package versions as strings to guess the active
  version despite no SemVer requirement in the package contract.
- Contract documents and the untyped runtime catalog used JSON last-key-wins
  behavior.

## Implementation

- Every runtime expert scope now binds `package_id`, `package_version`, and
  `expert_id` exactly.
- Signed composition validates duplicate manifests and bindings, resolves only
  the selected exact coordinates, and leaves unselected versions inactive.
- Canonical and packaged runtime configuration select version `1.0.2` for the
  two escalation experts and the exact `1.0.0` coordinate for other active
  experts.
- Strict contract JSON parsing rejects duplicate keys at any depth.
- The untyped model-catalog loader independently rejects duplicate keys and
  non-finite constants before routing interpretation.
- The integration maturity ledger now truthfully returns Expert Fabric to
  `production_wired` until this corrected candidate has installed evidence.

## Validation

- Ruff passed all changed source and tests.
- Mypy passed the corrected runtime catalog. A direct isolated check of the
  older generic schema codec still reports its existing jsonschema-stub and
  dynamic-decoder type debt; no new hook-specific error was introduced.
- 23 focused catalog/schema/coverage tests pass.
- A strict scan parsed 358 current config and generated-schema JSON files with
  zero duplicate keys.
- Canonical and packaged runtime catalog bytes are identical.

## Remaining work

- Run the complete suite after the continuing phase audit.
- Build and exercise the next signed installed candidate after all source gaps
  in this audit are closed.
- Physical remote, AppArmor/24-hour soak, independent human review, and final
  post-soak lifecycle gates remain unchanged.

## Decision

ADR 0159 records exact-coordinate activation and strict JSON. Do not restore a
"latest version" guess without first creating an explicit version-ordering
contract and migration.

