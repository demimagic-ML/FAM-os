# ADR 0166: Expert engineering scopes are advisory only

Status: Accepted

## Context

Phase 24 introduces machine-effect authorities that an owner may grant. Code
experts need signed scope to advise on tasks involving those powers, but a
model's capability manifest must not become an effect grant. Natural-language
intent and product presentation also need to name the same powers without
implying that execution occurred.

## Decision

Signed runtime code-expert scopes may declare `advisory_authorities` using the
complete `EngineeringAuthority` vocabulary. The catalog accepts this field only
for an expert whose signed manifest declares a `code.*` capability. The field
is descriptive routing authority to generate proposals; it contains no owner,
grant, target, duration, checkpoint, or revocation identity and therefore
cannot authorize an effect.

Core's deterministic action-intent firewall separately recognizes authority
requirements before model selection. Recognition adds requirements to the
decision but does not resolve a capability or mint a grant. Console and Shell
render strict engineering result discriminators with explicit proposed,
verified, published, and unavailable labels.

Integration coverage tracks each engineering authority independently. Until a
live owner-grant lifecycle and effect path have installed evidence, every new
authority remains `component_tested`, `production_reachable=false`, and
`installed_evidence=false`.

## Consequences

- A signed expert can be selected to discuss a high-risk task without receiving
  the requested machine power.
- Unknown, duplicate, or non-code advisory declarations fail catalog loading.
- Product surfaces cannot call a proposal a receipt or a publication proposal
  a completed publication.
- Runtime effect admission, grant persistence, and revocation remain mandatory
  later Phase 24 work.

## Alternatives considered

- Reuse expert capabilities as owner grants: rejected because package authors
  would control machine authority.
- Hide high-risk intents until providers exist: rejected because requests must
  fail closed with an accurate missing-authority explanation.
- Mark the engineering fabric production-wired because older workspace tools
  exist: rejected because none of the new general authorities has installed
  end-to-end evidence.

## Evidence

- `src/fam_os/core/production/action_intent.py`
- `src/fam_os/core/production/model_catalog_scopes.py`
- `configs/packages/runtime/model-catalog.json`
- `src/fam_os/shell/engineering_projection.py`
- `src/fam_os/console/static/task_updates.js`
- `configs/integration/coverage.json`
- `tests/unit/test_action_intent_firewall.py`
- `tests/unit/test_packaged_runtime_catalog.py`

## Superseded decisions

None. This narrows how the new engineering vocabulary participates in the
existing signed model-scope boundary from ADR 0158 and extends ADR 0165.
