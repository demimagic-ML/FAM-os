# FAM_OS Serialized Schemas

`v1alpha1/` contains generated JSON Schema Draft 2020-12 artifacts for every public Phase 2 wire-document root.

The files are generated from the typed domain contracts and the schema catalog. Do not edit individual schema JSON files by hand.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Alpha compatibility is exact-match. A decoder rejects unknown fields, missing canonical fields, unknown enum values, unknown schema families, future schema versions, and a contract version that does not match the selected schema.
