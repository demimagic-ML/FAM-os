# Reference expert packages

Phase 6.7 defines the first concrete local package set and binds each model to
an exact already installed Ollama artifact digest.

## Current definitions

| Role | Expert | Model | Tier |
|---|---|---|---|
| Language | `expert.language.llama3.2-3b` | `llama3.2:3b` | economical |
| Code | `expert.code.qwen2.5-coder-7b` | `qwen2.5-coder:7b` | economical |
| Retrieval embedding | `expert.retrieval.nomic-embed-text` | `nomic-embed-text:latest` | micro |
| Code escalation | `expert.code.laguna-xs2-33b` | `laguna-xs.2:q4_K_M` | escalation |
| Code escalation | `expert.code.gemma4-26b` | `gemma4:26b` | escalation |
| Python verification | `verifier.python.stable-toposort-v2` | deterministic local tests | verifier |

Laguna and Gemma are never economical/default tiers. Exact capability lookup
returns both as eligible escalation candidates, after which benchmark/resource
policy must decide whether either is justified.

## Runtime bindings

`fam.expert.runtime-binding/v1alpha1` joins an exact package coordinate to one
declared manifest artifact, provider-neutral runtime contract, runtime adapter,
opaque provider artifact reference, and expected SHA-256 digest. Bindings are
validated against manifests before installation or execution.

`OllamaModelCatalog` observes `/api/tags` and requires one exact installed name,
full SHA-256 digest, and positive size. `OllamaModelArtifactStore` lets the
durable lifecycle install a reference without copying model bytes. Verification
re-observes the digest. Removal deletes only FAM package state; it deliberately
does not delete user-owned Ollama downloads.

## Trust and licenses

The workstation package set is explicitly `local_unverified`, admitted only by
`local-workstation-development`. This is development trust, not a production
signature claim. The policy is default-denied elsewhere and never upgrades
these packages to signed or built-in.

Local `ollama show --license` evidence maps Qwen, Nomic, Laguna, and Gemma to
Apache-2.0. Llama retains an exact local license reference to its Llama 3.2
community terms. The audit summary is retained at
`artifacts/expert_fabric/phase6/license-audit.json`.

## Installation, updates, and rollback

`tools/install_reference_expert_packages.py` performs strict decoding, runtime
binding validation, live model-digest observation, trust validation, profile
compatibility, and lifecycle install/update. Its state and report are retained
under `artifacts/expert_fabric/phase6/`.

Laguna and Gemma versions 1.0.1 and 1.0.2 intentionally coexist. Version 1.0.1
is a complete manifest/binding rollback target; 1.0.2 is current. The rollback
proof re-hashes the installed model before switching to 1.0.1 and again before
restoring 1.0.2. It does not merely change an unverified pointer.

## Package-aware regression

`tools/run_packaged_strong_regression.py` requires an enabled installation,
exact digest/binding, and selection by declared `code.generate.python`
capability at escalation tier before starting the full-workstation Ollama
adapter. It emits both the privacy-scrubbed raw report and strict Phase 6
benchmark metadata.

The canonical capture is `artifacts/workstation/20260716T170632701276Z/`:

- Laguna includes one retained failed run and one independent
  `verified_after_repair` run. Both failed initial/repair candidates that used a
  forbidden set remain visible; the passing run succeeded after one bounded
  disclosed repair.
- Gemma independently passed on the initial attempt.
- Every successful run records CPU, RAM, VRAM, model transfer, storage I/O,
  latency, verifier outcome, package coordinate/version, state revision, and
  raw-evidence digest.
- All transient services ended `not-found`, `inactive`, and `dead`.
