# Serialized Schema and Compatibility Protocol

## Scope

Phase 2.7 defines the cross-process representation of the completed Phase 2 domain contracts. The serialized boundary consists of:

- self-describing JSON document envelopes;
- generated JSON Schema Draft 2020-12 artifacts;
- canonical encoders and strict typed decoders;
- exact-match registered-version compatibility admission;
- fixed compatibility fixtures;
- cross-contract identity and reference validation.

The schema boundary does not own domain meaning. Core, Routing, Application, Scheduler, Expert, Verification, Memory, and Registry dataclasses still enforce their component invariants.

## Wire envelope

Every document has exactly three top-level fields:

```json
{
  "schema_id": "fam.core.task-request/v1alpha1",
  "contract_version": "fam.core/v1alpha1",
  "payload": {}
}
```

`schema_id` identifies one serialized root and version. `contract_version` identifies the owning domain-contract family. `payload` contains the complete canonical dataclass representation. Domain roots that already carry `contract_version` retain that field, and both values must agree with the schema descriptor.

Unknown envelope or payload properties are rejected. Every dataclass field, including a field with a Python default, is required in the canonical wire shape. This prevents two producers from emitting different shapes for the same schema generation.

## Registered roots

The catalog currently contains 47 public document roots:

- Core task request, execution plan, and task result;
- routing request and result;
- Application identity, instance, capability, registry entry, permission grant, observation request/result, action preparation/proposal/confirmation/result, connector registration/event, and Application failure;
- host inventory and effective resource budget;
- expert manifest `v1alpha1` and `v1alpha2`, plus verifier, connector, and memory-record manifests;
- Core failure envelope and degradation notice.
- scheduler defaults, validation profile, user policy, session override, discovered state, composition request, and composed resource configuration.
- the concrete validation-profile document combining scheduler policy with a service envelope.
- FAM Shell ask, decision, cancellation, snapshot-query, and snapshot documents.
- application action-audit intent and chained-record documents.
- Registry package signature, trust policy, and validation-report documents.
- Expert host/profile compatibility report.

Nested dataclasses, enums, tuples, timestamps, package metadata, metrics, hardware tiers, condition evidence, and immutable JSON payloads are described in each root's `$defs`.

## Decision coverage

Every public Phase 2 family and the compatibility policy has an accepted decision record:

| Public family | Decision |
|---|---|
| Application identity, capability, permission, observation, action, and connector documents | ADR 0013 |
| Core request, execution plan, result, and routing documents | ADR 0014 |
| Host inventory and effective resource budget | ADR 0015 |
| Expert, verifier, connector, package, and memory-record manifests | ADR 0016 |
| Core and Application failures plus degradation | ADR 0017 |
| Wire envelope, strict decoding, generated schemas, compatibility, and cross-references | ADR 0018 |
| Configuration sources, authority precedence, monotonic restrictions, and composition | ADR 0019 |
| Concrete compatibility/full profile documents and service envelopes | ADR 0020 |
| Package signature, trust policy, and validation evidence | ADR 0053 |
| Expert host/profile compatibility evidence | ADR 0054 |

## Canonical encoding

`dumps_document` emits UTF-8-compatible JSON text with sorted object keys, compact separators, explicit defaulted fields, enum values, timezone-bearing ISO 8601 timestamps, arrays for tuples, and objects for immutable mappings. Non-finite numbers and unsupported Python values are rejected.

Canonical encoding is stable for the same admitted domain value. It is not a cryptographic signature format. Phase 6 must define signed package canonicalization and digest policy independently.

## Strict decoding

Decoding proceeds in a fixed order:

1. Parse strict JSON and reject `NaN`, positive infinity, and negative infinity.
2. Read the self-describing schema and contract identities.
3. Apply compatibility admission before interpreting the payload.
4. Validate the complete envelope against its Draft 2020-12 schema, including timestamp formats.
5. Decode fields to typed enums, tuples, mappings, timestamps, and dataclasses.
6. Run the owning dataclass constructors so component invariants remain authoritative.

Validation errors expose a structural path and validator keyword without copying rejected values into the message.

## Alpha compatibility policy

All registered schemas use `CompatibilityPolicy.EXACT`.

- A known schema version and its exact declared contract version are accepted.
- An unknown schema family is rejected.
- A known family with an unregistered alpha or stable version is rejected.
- A mismatched contract-family version is rejected.
- Unknown enum values, unknown fields, and missing fields are rejected.
- No implicit additive compatibility, field dropping, enum coercion, or best-effort migration is allowed.

Any future version requires a new descriptor, generated artifact, fixed fixtures, compatibility tests, and an explicit migration registered by a later ADR. Alpha status does not permit silent wire changes inside an existing version. Expert manifest `v1alpha1` and `v1alpha2` are the first side-by-side exact versions; ADR 0051 owns that migration.

## Generated artifacts

Checked artifacts live in version-owned `schemas/v1alpha*/` directories. They
are generated deterministically from the schema catalog and domain annotations:

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

The second command fails when any artifact is missing or differs from the current catalog. Every generated document is checked with `Draft202012Validator.check_schema` in the contract test suite.

## Fixed compatibility fixtures

`tests/fixtures/schema_compatibility/v1alpha1/` contains immutable examples for a current valid document, a document with an unknown field, and a future-version document. Tests prove that the first remains decodable and the other two remain rejected.

## Cross-contract validation

Individual schema validity is necessary but not sufficient. `ContractReferenceSet` validates a decoded set without reaching into provider adapters or storage:

- duplicate request, plan, inventory, budget, expert, verifier, connector, and memory-record identities are rejected;
- plans and results reference known requests and results reference a matching plan;
- budgets reference a known inventory and only its accelerators and storage tiers;
- positive SSD cache budgets use inventory tiers declared cache-eligible;
- experts reference known verifiers;
- verifier, connector-capability, and memory-content schema references exist in the supplied schema index;
- memory provenance references known parent records.

Reference issues use stable codes and safe messages. The caller decides whether to collect the full issue tuple or require a valid set and fail admission.

## Boundaries and deferred work

- Schema validation does not authenticate a sender or connector; Phase 5 owns authenticated local transport.
- Schema validation does not grant permission, verify signatures, trust packages, select experts, allocate hardware, or release model output.
- Capability-specific input/output schemas are referenced by ID but remain owned by their packages and future registry.
- Transport message-size, rate, and connection limits remain part of the concrete authenticated transport boundary.
- Version migration is intentionally absent because no second version exists. It must never be inferred from field similarity.
