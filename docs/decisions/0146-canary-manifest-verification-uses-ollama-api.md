# ADR 0146: Canary manifest verification uses the Ollama API

Status: Accepted

## Context

The physical specialist imported successfully into Ollama 0.30, but canary
verification called `ollama show MODEL --json`. That CLI flag is unavailable on
the installed version, so the canary emitted a signed denial before inference.
The command-line surface is intended for humans and has changed; the local HTTP
API exposes structured model details and catalog state directly.

## Decision

Keep bounded CLI calls for local `create` and `rm`, but verify the created model
through `POST /api/show` and check presence/removal through `GET /api/tags`.
Canonical JSON from the show response is size-bounded and hashed into the canary
report. Catalog shapes and model identities are validated before use.

If creation succeeds but manifest retrieval or validation fails, the installer
immediately removes the newly imported model and confirms its absence. Canary
failure cannot leave a qualification model installed.

## Consequences

- Manifest verification works across the current Ollama CLI surface.
- FAM depends on the documented, structured local API instead of parsing human
  CLI output.
- Create-time partial success is explicitly rolled back.
- Removal is confirmed by an independent catalog observation.

## Alternatives considered

- Parsing `ollama show` text was rejected because it is human-oriented and not
  a stable typed contract.
- Pinning an older Ollama binary was rejected because the product already uses a
  newer compatible API and should not regress the workstation runtime.
- Treating a successful create exit code as sufficient was rejected because the
  canary must bind an observed runtime manifest.

## Evidence

- `src/fam_os/adapters/ollama/canary_installer.py`
- `tests/unit/test_ollama_canary_installer.py`
- [Ollama show API](https://docs.ollama.com/api-reference/show-model-details)
- [Ollama list models API](https://docs.ollama.com/api/tags)
