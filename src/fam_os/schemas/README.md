# Serialized Schema Boundary

This package owns only cross-process document mechanics:

- versioned schema identity and exact alpha compatibility admission;
- canonical JSON encoding and strict typed decoding;
- Draft 2020-12 JSON Schema generation and validation;
- cross-contract reference validation after individual documents are valid.

Domain meaning remains in Core, Routing, Scheduler, Application, Expert, Verification, Memory, and Registry components. This package must not add provider fields, runtime policy, package trust, permission decisions, or hardware discovery.

Generated schemas live under `schemas/v1alpha1/`. Update them with `tools/render_contract_schemas.py` and verify them with `--check`.
