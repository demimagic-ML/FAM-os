# ADR 0018: Strict self-describing serialized schemas and exact alpha compatibility

**Status:** Accepted  
**Date:** 2026-07-16

## Context

Phase 2 domain contracts were immutable typed Python objects with version markers, but no machine-readable cross-process representation existed. A connector, local service, package registry, configuration loader, or future client could otherwise choose its own field defaults, enum coercion, timestamp representation, and unknown-field behavior.

The current families are alpha contracts. Alpha permits deliberate replacement by a new version; it must not permit silent mutation of documents already labeled `v1alpha1`.

## Decision

FAM_OS uses a self-describing JSON envelope containing `schema_id`, `contract_version`, and `payload`. Public serialized roots are registered with an owning domain type and exact compatibility policy. JSON Schema Draft 2020-12 artifacts are generated deterministically and checked into `schemas/v1alpha1/` for non-Python consumers.

All current `v1alpha1` schemas require exact identity and exact canonical shape. Unknown fields, missing defaulted fields, unknown enum values, unknown families, future versions, contract-version mismatches, non-finite numbers, and domain-invalid values are rejected. There is no implicit migration or best-effort field dropping.

Encoding is canonical for admitted values: keys are sorted, tuples become arrays, enums become their declared values, datetimes retain timezone offsets, immutable JSON mappings become objects, and every dataclass field is present.

Decoding validates the JSON Schema before constructing domain dataclasses, then invokes the owning component's constructor invariants. Schema mechanics live in `fam_os.schemas`; domain semantics remain with their components.

Cross-contract validation is a separate pass over already decoded objects. It checks duplicate identities and request/plan/result, inventory/budget, expert/verifier, schema-reference, and memory-provenance links without turning the serializer into orchestration policy.

## Consequences

- Python and non-Python processes can consume the same checked schema artifacts.
- A document identifies both its serialized root and owning contract family before payload interpretation.
- Producers cannot omit defaults or add speculative fields while claiming the same schema version.
- Domain constructors remain the final authority for semantic invariants.
- Future compatible or migrated versions require explicit descriptors, fixtures, tests, and an ADR.
- Generated artifacts must be refreshed and checked whenever a registered domain annotation changes.
- The implementation adds the `jsonschema` runtime dependency for standards-based validation and format checking.
- Authenticated transport, message-size/rate limits, package signature validation, and capability-specific schema installation remain later-phase responsibilities.

## Alternatives considered

1. Serialize dataclasses with `asdict` only: rejected because it provides no strict decoder, version admission, enum policy, or cross-language schema.
2. Hand-maintain JSON Schema files separately: rejected because schema and Python annotations would drift without deterministic generation and round-trip coverage.
3. Accept unknown fields for forward compatibility: rejected for alpha security-sensitive local boundaries because a field ignored by one process could be acted on by another.
4. Treat missing defaulted fields as equivalent: rejected because it permits multiple wire shapes and makes future default changes ambiguous.
5. Use pickle or another Python-specific object format: rejected because connectors and clients will include non-Python implementations and untrusted packages.
6. Put reference validation in each decoder: rejected because individual document validity and relationships among a selected document set have different ownership and lifecycle.
7. Implement speculative migrations now: rejected because no second schema version exists and an untested migration would create false compatibility.

## Evidence

- `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md`
- `src/fam_os/schemas/`
- `schemas/v1alpha1/`
- `tools/render_contract_schemas.py`
- `tests/contract/test_schema_roundtrip.py`
- `tests/contract/test_schema_compatibility.py`
- `tests/contract/test_cross_contract_references.py`
- `tests/fixtures/schema_compatibility/v1alpha1/`
