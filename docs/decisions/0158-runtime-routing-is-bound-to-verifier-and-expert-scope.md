# ADR 0158: Runtime routing is bound to verifier and expert scope

Status: Accepted

## Context

The installed runtime catalog declared verifier IDs on each physical model, but
selection did not require the chosen model to declare the request's verifier.
Signed packages that shared one Ollama artifact were also collapsed to one
arbitrary provenance. Disabling one Llama or Qwen-VL expert therefore retained
the aggregate model intents, peer declarations attributed all capabilities to
one package, and factory specialists could claim an already-owned model
reference.

## Decision

Runtime authority is represented at two separate levels:

- A model entry describes one physical local artifact and the union of routes
  and verifier bindings it can support.
- A signed expert provenance describes the exact subset of intents and verifier
  IDs supplied by one signed expert package.

The signed runtime configuration must declare an `expert_scopes` entry for
every selected expert binding. Scope intents must be backed by the manifest's
capability domains, scope verifier IDs must be declared by that manifest, and
the exact union of all scopes must equal the aggregate model entry. Missing,
duplicate, mismatched, or unsupported scopes fail catalog composition.

Selection for a verified request filters candidates by the durable declaration's
exact verifier ID. Initial, repair, escalation, remote recovery, and fallback
selection use the same requirement. No compatible local model means a
fail-closed routing error before inference.

Expert enablement filters provenance first and rebuilds each shared model's
effective intents and verifiers from the remaining scopes. Durable state stores
the scoped entry, current signed experts are never reintroduced from an old
aggregate row, and non-release rows are restored only when an exact Expert
Factory lineage exists.

Peer capability declarations are issued per enabled expert scope. Residency
continues to own one lease per physical artifact; a shared artifact receives a
deterministic runtime identity rather than an arbitrary package identity.
Factory activation validates verifier availability, scope, and model-reference
ownership before lifecycle or storage mutation.

## Consequences

- Disabling the Llama math expert removes only the math route and verifier while
  the language and retrieval scopes may continue using the same loaded model.
- A peer cannot advertise the aggregate abilities of several packages under one
  arbitrary expert ID.
- A factory specialist cannot replace a signed model by reusing its model
  reference.
- Signed catalog configuration is more explicit and rejects older aggregate-only
  documents until they are rebuilt with expert scopes.
- Residency evidence remains artifact-oriented and does not double-count shared
  weights.

## Alternatives considered

- Keep verifier declarations informational: rejected because verified routing
  could choose a model without the declared verification contract.
- Duplicate a model entry for every package: rejected because residency and
  resource accounting would represent one physical artifact several times.
- Disable every package sharing a model as one unit: rejected because package
  enablement and capability authority are independently signed.
- Infer scopes from capability names at startup: rejected because inference
  cannot express intentional subsets and makes signed configuration ambiguous.

## Evidence

- `src/fam_os/core/production/model_catalog.py`
- `src/fam_os/core/production/model_selection.py`
- `src/fam_os/product/service.py`
- `src/fam_os/product/peer_capabilities.py`
- `src/fam_os/product/model_residency.py`
- `src/fam_os/product/factory_activation.py`
- `configs/packages/runtime/model-catalog.json`
- `tests/unit/test_packaged_runtime_catalog.py`
- `tests/unit/test_peer_capabilities.py`
- `tests/unit/test_factory_activation_product.py`
- `tests/integration/test_reference_expert_package_definitions.py`

