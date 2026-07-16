# Handoff 0017: Strict serialized schemas and compatibility

**Date:** 2026-07-16  
**Plan step:** Phase 2.7 and 2.10  
**Status:** Complete  
**Previous handoff:** `0016-structured-failures-degradation.md`

## Objective

Create a machine-validated cross-process representation for every completed Phase 2 public contract family, define compatibility behavior that cannot silently reinterpret alpha documents, and validate references that span individually valid documents.

## Scope completed

- Added a self-describing JSON envelope with exact `schema_id`, `contract_version`, and `payload` fields.
- Registered 27 public serialized document roots across Core, Routing, Application, Scheduler, Expert, Verification, Connector, Memory, failure, and degradation contracts.
- Added deterministic JSON Schema Draft 2020-12 generation from domain dataclass annotations.
- Materialized and checked 27 cross-language artifacts under `schemas/v1alpha1/`.
- Added canonical JSON encoding for dataclasses, enums, tuples, timezone-aware timestamps, immutable mappings, and finite JSON values.
- Added strict parsing and typed decoding back into the owning domain dataclasses.
- Required every canonical dataclass field, including Python-defaulted fields, and rejected unknown envelope or nested fields.
- Added exact-match `v1alpha1` compatibility admission with distinct unknown-family, unsupported-version, and contract-version-mismatch failures.
- Rejected unknown enum values, non-finite JSON values, invalid timestamp formats, and values that fail component domain invariants.
- Added fixed current, unknown-field, and future-version compatibility fixtures.
- Added cross-contract validation for duplicate identities and Core, hardware, verifier, connector-schema, memory-schema, and provenance references.
- Kept schema mechanics separate from domain semantics and concrete providers.
- Added the `jsonschema` dependency for standards-based Draft 2020-12 and format validation.
- Added ADR 0018 and an explicit decision-coverage table proving that every current public schema family and compatibility policy has an accepted ADR.
- Marked Master Plan steps 2.7 and 2.10 complete.

## Explicitly not completed

- No second schema version or speculative migration was added.
- No authenticated Unix socket, MCP session, HTTP endpoint, connector transport, or client SDK was implemented.
- No transport message-size, connection, or rate limit was selected.
- No capability-specific schema package installer or registry was implemented; reference validation consumes a supplied known-schema index.
- No package signature canonicalization or cryptographic signing format was defined.
- No configuration-layer schemas were added; that is Phase 2.8.
- No concrete validation-profile documents were added; that is Phase 2.11.
- No permission, trust, scheduling, allocation, verification, or final-release decision is granted by schema validity.

## Architecture and decisions

ADR 0018 makes alpha compatibility strict. A producer may not add a field, omit a default, introduce an enum value, or otherwise change a document while continuing to label it `v1alpha1`. A future change creates a new schema descriptor and artifact plus explicit compatibility and migration evidence.

The envelope identifies the serialized root separately from its owning domain-contract family. Application action results, for example, use their Application schema identity while nested failure objects retain the Application failure contract version. Domain roots that already contain `contract_version` carry it in the payload as well, and the generated schema fixes it to the descriptor's expected value.

Schema validation and domain validation are intentionally layered. Draft 2020-12 handles the complete structural shape and timestamp format. Typed decoding then reconstructs tuples, enums, mappings, datetimes, and dataclasses. The component constructor remains authoritative for semantic relationships such as plan graph safety, permission scope, status/failure agreement, resource ceilings, and manifest invariants.

Cross-contract validation runs only after individual documents decode. This prevents the codec from becoming a god policy module and lets callers validate the exact admitted document set for one registry, request lifecycle, hardware snapshot, or memory graph.

The source modules remain bounded. The largest new implementation module is `schemas/codec.py` at 213 lines, all implementation modules remain below 300 lines, and all functions remain below 50 lines.

## Files changed

| Path | Purpose |
|---|---|
| `pyproject.toml` | Standards-based JSON Schema runtime dependency |
| `src/fam_os/schemas/descriptor.py` | Schema identity and compatibility-policy descriptor |
| `src/fam_os/schemas/errors.py` | Safe schema, compatibility, and reference errors |
| `src/fam_os/schemas/type_support.py` | Annotation and finite JSON-value mechanics |
| `src/fam_os/schemas/schema_builder.py` | Deterministic Draft 2020-12 generation |
| `src/fam_os/schemas/catalog.py` | Twenty-seven public document-root registrations |
| `src/fam_os/schemas/compatibility.py` | Exact alpha compatibility admission |
| `src/fam_os/schemas/codec.py` | Canonical encoder, strict JSON parser, validator, and typed decoder |
| `src/fam_os/schemas/references.py` | Cross-document identity and reference validation |
| `src/fam_os/schemas/__init__.py` | Public schema boundary exports |
| `src/fam_os/schemas/README.md` | Schema component ownership |
| `tools/render_contract_schemas.py` | Bounded schema artifact renderer/checker |
| `schemas/v1alpha1/*.schema.json` | Twenty-seven generated cross-language schemas |
| `schemas/README.md` | Generated artifact workflow |
| `tests/contract/schema_*_fixtures.py` | Representative value builders for every registered root |
| `tests/contract/test_schema_roundtrip.py` | Catalog completeness, canonical round-trip, and schema validity |
| `tests/contract/test_schema_compatibility.py` | Strict fields, versions, enums, fixtures, and domain validation |
| `tests/contract/test_cross_contract_references.py` | Duplicate and cross-family reference tests |
| `tests/fixtures/schema_compatibility/v1alpha1/` | Fixed valid and rejected alpha documents |
| `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md` | Wire envelope, compatibility, artifacts, and reference protocol |
| `docs/decisions/0018-strict-serialized-schema-compatibility.md` | Public wire and compatibility decision |
| `docs/protocols/CORE_CONTRACTS.md` | Serialized Core boundary link |
| `docs/protocols/APPLICATION_CONTRACTS.md` | Serialized Application boundary link |
| `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md` | Serialized hardware boundary link |
| `docs/protocols/MANIFEST_CONTRACTS.md` | Serialized manifest boundary link |
| `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md` | Serialized failure boundary link |
| `docs/PROJECT_STRUCTURE.md` | Schema-mechanics component placement |
| `MASTER_PLAN.md` | Phase 2.7/2.10 completion and Phase 2.8 entry point |
| `README.md` | Current implementation and next-step status |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0017-strict-schema-compatibility.md` | This implementation record |

## Public interfaces

- `CompatibilityPolicy`
- `SchemaDescriptor`
- `CompatibilityReport`
- `SCHEMA_DESCRIPTORS`
- `build_schema`
- `descriptor_for_schema`
- `descriptor_for_type`
- `compatibility_report`
- `require_compatible`
- `encode_document`
- `dumps_document`
- `decode_document`
- `loads_document`
- `ContractReferenceSet`
- `ReferenceIssue`
- `find_reference_issues`
- `require_valid_references`
- `ContractSchemaError`
- `UnknownSchemaError`
- `UnsupportedSchemaVersionError`
- `ContractVersionMismatchError`
- `SchemaEncodingError`
- `SchemaValidationError`
- `CrossContractValidationError`

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: all 23 focused contract tests passed in 0.074 seconds; 0 failures.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: all 216 FAM_OS tests passed in 0.116 seconds; 0 failures. The previous suite contained 193 tests.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: all 27 generated schema artifacts exactly match the catalog and annotations.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|ollama|systemd|subprocess|vscode|WorkspaceEdit|MCP|mcp" \
  src/fam_os/schemas tools/render_contract_schemas.py
```

Result: no inference provider, service manager, subprocess, editor SDK, or connector protocol dependency was found.

An AST size audit found no implementation module at or above 300 lines and no function at or above 50 lines. The generated artifact count is exactly 27.

## Evidence and artifacts

- `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md`
- `docs/decisions/0018-strict-serialized-schema-compatibility.md`
- `schemas/v1alpha1/`
- `tests/contract/test_schema_roundtrip.py`
- `tests/contract/test_schema_compatibility.py`
- `tests/contract/test_cross_contract_references.py`
- `tests/fixtures/schema_compatibility/v1alpha1/`
- Public family decisions: ADR 0013 through ADR 0017

## Known limitations and risks

- Exact alpha compatibility intentionally provides no migration path until a second version has real semantics and fixtures.
- JSON Schema captures structural types and timestamp format, while several semantic invariants are enforced only during typed domain construction. Non-Python consumers must reproduce those documented domain invariants before admission.
- Generated `$defs` currently require unique dataclass class names within one document graph; a future same-name type collision must use qualified definition identities.
- Capability, verifier evidence, and memory content schema IDs are references. Installation, trust, and persistence of those schema packages remain future registry work.
- `ContractReferenceSet` treats its memory-record set as closed when checking parents. A future persistent store may require an explicit trusted resolver for parents outside one batch.
- Transport size, nesting, rate, authentication, replay, and connection policies are not properties of these domain schemas and must be enforced by Phase 5's local transport.
- Canonical JSON here is stable encoding for comparison and fixtures, not a signature canonicalization standard.
- The artifact renderer writes generated files; hand editing an individual schema will be detected and rejected by `--check`.

## Operational notes

This change generated repository artifacts and ran in-memory validators only. It opened no socket, contacted no provider, loaded no model, changed no service, executed no connector, allocated no hardware budget, and persisted no user memory.

## Recommended next entry point

Begin Phase 2.8. Read this handoff, the hardware resource contracts, ADR 0015, dual-profile ADR 0011, and the current small `ResourceBudget` compatibility path. Define separate versioned configuration inputs for safe defaults, discovered inventory/enforcement, named validation profile, user policy restriction, and session override. Composition must be deterministic, auditable, and monotonic: a weaker or later layer may restrict authority but cannot invent hardware, exceed a cgroup/host ceiling, enable an unavailable accelerator, or convert SSD capacity into memory.
