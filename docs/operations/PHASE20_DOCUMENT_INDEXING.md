# Phase 20.2 signed document-index qualification

Run the fresh installed gate with:

```bash
.verification-venv/bin/python -m tools.run_phase20_index_exit
```

The gate builds and signs a seven-component release, installs it privately, and
starts only the installed Python package with deterministic embeddings. It
proves empty-by-default behavior, authenticated and CSRF-protected opt-in,
unconfirmed denial, recursive folder and single-file grants, extension bounds,
symlink exclusion, short-grant expiry and cascade deletion, encrypted durable
payloads, cross-Console visibility for the same owner, restart persistence for
an active grant, healthy diagnosis, and complete removal.

Raw evidence is written to
`artifacts/memory/phase20.2-document-indexing.json`.

## Console API

After exchanging the launcher token for an HttpOnly Console session, submit:

```http
POST /api/v1/memory/indexes
Origin: http://127.0.0.1:<port>
X-CSRF-Token: <session csrf token>
Content-Type: application/json

{
  "path": "/home/user/project",
  "kind": "folder",
  "recursive": true,
  "purpose_ids": ["assist"],
  "workspace_ids": ["project"],
  "allowed_extensions": [".md", ".py", ".txt"],
  "max_files": 128,
  "max_file_bytes": 1048576,
  "max_total_bytes": 16777216,
  "expires_in_hours": 168,
  "confirmed": true
}
```

Use `GET /api/v1/memory/indexes` with the authenticated session to list active
grants. `expires_in_seconds` is available for precise short-lived grants and is
mutually exclusive with `expires_in_hours`. The server assigns owner, grant ID,
model identity, artifact digest, approval time, and absolute expiry. Unsupported
or unknown fields fail closed.

This API creates and lists approved indexes. It does not yet inject retrieval
into answers; that is the Phase 20.3 gate. Full correction, export, manual
expiry, deletion, and durable management receipts are Phase 20.4.
