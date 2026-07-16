# Handoff 0058: Reference expert packages

**Date:** 2026-07-16  
**Plan step:** Phase 6.7 and Phase 6 exit gate  
**Status:** Complete  
**Previous handoff:** `0057-expert-routing-benchmark-metadata.md`

## Objective

Define, install, select, activate, update, and roll back the first concrete
language, code, retrieval, verifier, Laguna, and Gemma packages, then complete
the mandatory package-aware strong-model regression without making large models
defaults.

## Scope completed

- Exact package manifests for Llama language, Qwen economical code, Nomic
  retrieval embedding, Laguna escalation code, and Gemma escalation code.
- Deterministic stable-toposort v2 verifier package definition.
- Strict runtime-binding schema joining package coordinates to exact installed
  Ollama references and full SHA-256 digests.
- Live strict Ollama model catalog and non-copying external artifact store.
- Explicit `local-workstation-development` trust; no false signed/built-in claim.
- Local license audit and corrected Apache-2.0 metadata for Qwen, Nomic, Laguna,
  and Gemma plus a Llama community-license reference.
- Durable installation of all model experts under full-reference compatibility.
- Laguna/Gemma 1.0.1 rollback definitions retained beside current 1.0.2.
- Real digest-reverified rollback to 1.0.1 and restore to 1.0.2 for both strong
  experts, ending at installation-state revision 17.
- Exact declared-capability/tier resolver joining registry, enabled lifecycle
  state, and runtime bindings.
- Package-aware full-workstation benchmark wrapper and strict metadata emission.
- Canonical independent Laguna and Gemma runs plus retained Laguna failure
  evidence showing nondeterministic repair reliability.

## Explicitly not completed

- Packages remain local-unverified development artifacts; Phase 13.7 owns signed
  publication.
- The installer does not download or delete Ollama models.
- General quality/cost policy across task families remains Phase 9.
- Live placement, context budgeting, cache, and eviction remain Phase 7.

## Architecture and decisions

ADR 0057 makes external runtime artifacts exact digest-bound package inputs
without transferring deletion ownership. Complete manifests/bindings are
retained for rollback. Strong models are escalation candidates only. Package
benchmarks must cross trust, compatibility, lifecycle, capability, binding,
runtime, verification, and hardware-evidence boundaries.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/experts/runtime_binding.py` | Exact runtime artifact binding contract. |
| `src/fam_os/experts/installed_candidates.py` | Enabled declared-capability resolution. |
| `src/fam_os/registry/runtime_artifacts.py` | Runtime artifact observation port. |
| `src/fam_os/adapters/ollama/model_catalog.py` | Strict installed model observations. |
| `src/fam_os/adapters/ollama/artifact_store.py` | Non-copying lifecycle artifact store. |
| `configs/packages/` | Expert, verifier, binding, and trust documents. |
| `tools/install_reference_expert_packages.py` | Validated install/update composition. |
| `tools/verify_reference_package_rollback.py` | Real rollback/restore proof. |
| `tools/run_packaged_strong_regression.py` | Package-gated workstation regression. |
| `tests/unit/test_ollama_expert_packages.py` | Catalog/store/binding tests. |
| `tests/integration/test_reference_expert_package_definitions.py` | Definition and capability-resolution tests. |
| `docs/protocols/REFERENCE_EXPERT_PACKAGES.md` | Package semantics and evidence. |
| `docs/decisions/0057-reference-runtime-artifacts-and-development-trust.md` | Artifact/trust decision. |

## Public interfaces

- `EXPERT_RUNTIME_BINDING_VERSION`, `ExpertRuntimeBinding`
- `validate_runtime_binding`
- `RuntimeArtifactObservation`, `RuntimeArtifactCatalog`
- `OllamaModelCatalog`, `OllamaModelArtifactStore`
- `InstalledExpertCandidate`, `InstalledExpertCandidateResolver`
- `require_successful_stable_toposort_regression`
- `fam.expert.runtime-binding/v1alpha1`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST implementation file/function size gate>
python3 <canonical Phase 6 raw/metadata/digest/privacy/package/resource gate>
systemctl --user show fam-parity-ollama.service -p LoadState -p ActiveState -p SubState --value
```

Result: all 51 schemas and compileall passed. Both Python environments passed
600 tests with three expected environment-dependent skips. The size gate found
no implementation file above 300 lines and no function above 50 lines across
351 source/tool files. The canonical Phase 6 gate validated three raw reports
and three strict digest-linked metadata documents: one retained Laguna failure,
one Laguna `verified_after_repair` success, and one Gemma `verified_initial`
success. Every successful report contained complete CPU/RAM/VRAM/model/storage
evidence, package version 1.0.2, lifecycle revision 17, capability/tier
selection, privacy scrubbing, and a passing smoke gate. The transient service
ended not-found/inactive/dead. Larry indexed 919 files / 2,643 symbols with
14,924 nodes / 50,652 edges; freshness and verification were clean. The code
knowledge graph was independently refreshed to the same 14,924-node /
50,652-edge view.

## Evidence and artifacts

- `artifacts/expert_fabric/phase6/installation-state.json`
- `artifacts/expert_fabric/phase6/install-report.json`
- `artifacts/expert_fabric/phase6/rollback-report.json`
- `artifacts/expert_fabric/phase6/license-audit.json`
- `artifacts/workstation/20260716T170632701276Z/`
- `schemas/v1alpha1/fam.expert.runtime-binding.schema.json`

## Known limitations and risks

- Laguna produced a failed bounded repair in addition to a successful bounded
  repair. The failure is retained and shows that one successful run does not
  establish high reliability.
- `local_unverified` packages are suitable only for this explicit development
  policy.
- Ollama tag changes fail digest verification and require a new package version.
- Host-root storage counters include unrelated activity during each run window.

## Operational notes

No model was downloaded, copied, deleted, or modified. The main Ollama service
was not replaced. Benchmark transient services ended not-found/inactive/dead.
Current strong versions are 1.0.2; rollback versions 1.0.1 remain disabled and
available.

## Recommended next entry point

Begin Phase 7.1. Read current cgroup observation adapters/contracts, hardware
resource contracts, profile composition, package resource requirements, and
the Phase 6 workstation evidence before defining repeated live scheduler input.
