# Handoff 0166: Real Expert Factory signed-installed exit

**Date:** 2026-07-18  
**Plan step:** Phase 22.1-22.8  
**Status:** Complete  
**Previous handoff:** `0165-typed-held-out-learning-curve.md`

## Objective

Correct the remaining representation and product-integration defects, produce a
promotable physical QLoRA specialist, and qualify its complete conversion,
signed package, canary, activation, rollback, reactivation, retirement, audit,
and removal lifecycle from a fresh signed FAM_OS installation.

## Scope completed

- Matched QLoRA records to production Qwen chat serving with explicit
  user/assistant messages, `enable_thinking=false`, completion-only loss, and
  tokenizer EOS.
- Standardized every local product/factory owner namespace on the decimal Unix
  UID and repeated training/evaluation instead of migrating signed evidence.
- Ran the canonical RTX 5080 `diverse2500` checkpoint with 2,868 verified
  fixtures, 2,500 train, 312 validation, and 56 held-out records.
- Obtained a signed promotable comparison with 100% quality, zero safety and
  policy failures, 83.33% unrelated quality, and no promotion reason codes.
- Corrected release-root composition, stable conversion-environment identity,
  retry-scoped one-use IDs, supported systemd scope properties, hermetic
  conversion identity/caches, expert capability mapping, and Ollama API-based
  canary manifest/removal verification.
- Converted the physical candidate to Q8_0 base plus F16 adapter, signed and
  installed it disabled, passed the production Python canary, activated,
  manually rolled back, reactivated, retired, removed runtime/artifact bytes,
  and retained audit receipts.
- Built a fresh seven-component Ed25519-signed FAM_OS release and repeated the
  same lifecycle with `fam_os` imported from its installed tree.
- Sealed one aggregate content-free exit document and completely removed the
  ephemeral signed qualification installation.

## Explicitly not completed

- Phase 21.7 still needs a second physical Linux machine; this Phase 22 exit is
  single-workstation evidence.
- Phase 23 release matrices, 24-hour soak, and independent human security review
  remain open.
- The qualification specialist is intentionally retired at the end of the exit;
  the audit proves it can be rebuilt and activated but does not leave it enabled
  for ordinary user tasks.

## Architecture and decisions

- ADR 0141 requires training and serving to use the same chat template.
- ADR 0142 defines the canonical local owner as the decimal Unix UID.
- ADR 0143 excludes observation time from immutable conversion identity.
- ADR 0144 keeps output enforcement at the supported isolated-worker and trusted
  parent boundaries instead of an unsupported scope property.
- ADR 0145 gives the conversion sandbox an ephemeral identity and `/tmp` caches.
- ADR 0146 uses Ollama's structured API for canary manifest and catalog checks.

## Principal files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/training/qlora_worker.py` | Serving-compatible Qwen SFT records |
| `src/fam_os/product/owner_identity.py` | Canonical local owner constructor |
| `src/fam_os/expert_factory/conversion.py` | Stable immutable environment identity |
| `src/fam_os/product/storage/factory_conversion_repository.py` | Idempotent repeated observations |
| `src/fam_os/adapters/training/isolated_conversion_command.py` | Supported scope limits and hermetic environment |
| `src/fam_os/adapters/ollama/canary_installer.py` | API manifest verification and confirmed cleanup |
| `tools/phase22_release_exit/` | Physical release and aggregate exit orchestration |
| `tools/run_phase22_final_exit.py` | Signed-installed aggregate sealing and removal |
| `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md` | Completed production exit evidence |

## Physical evidence

Training/evaluation:

- Run: `phase22-stable-toposort-diverse2500-chat-20260718-03`
- Adapter: `fba7c074f68fcc83f70d2aab8f07aad2ca924991997c5dc21d7b3bfc6c4695fa`
- Signed decision: `192299eb3aa808175c577aa6003f705b62a02ba638737abb489d40f1949c40f9`
- Sealed suite: `21773b83ded29b5e0ac5aed3220db140f5fae216f2fcca976e3d1450ac1d2684`
- Training peak: 1,767,436,288 RAM bytes, 7,463,763,968 VRAM bytes,
  72 C, 204,247 J.
- Candidate evaluation: 5,471,080 us p95, 5,904,084,992 RAM bytes,
  1,590,149,632 VRAM bytes, 39,558 J.

Signed-installed release:

- Attempt: `release-attempt-10-installed`
- Base GGUF: 2,165,039,328 bytes; adapter GGUF: 34,892,384 bytes.
- Package: `fam.specialist.stable-toposort` version
  `1.0.0-attempt-10-installed`, initially disabled.
- Canary: 1/1 passed, zero verifier failures, outputs discarded.
- Installed module digest:
  `e7440068b925062869aacdca7871767130ce432f73bfbec4c9b7c4a243ccb186`.
- Signed release manifest:
  `6129d2273fc04636e697e157e288aa2de0675b9c04874e8ae2296cc7c61e366c`.

Authoritative artifacts:

- `artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/evidence.json`
- `artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/release-attempt-10-installed/release-evidence.json`
- `artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/phase22-exit-evidence.json`

## Failed-closed history

The preserved attempts are part of the evidence, not ignored retries:

- Canonical run 02 denied training while an Ollama embedding model remained
  resident.
- Release attempts 01-02 exposed the nested state-root mismatch and timestamped
  conversion identity.
- Attempts 03-05 exposed unsupported scope properties and missing hermetic cache
  identity.
- Attempts 06-07 reached packaging/canary and exposed the intent-capability
  mismatch plus obsolete CLI JSON behavior.
- Attempt 08 passed from source; attempts 09-10 passed from the signed installed
  product, with attempt 10 carrying the executed module digest.

No failed attempt's approval, signed decision, or output was copied into a later
attempt. Retry identities are one-use and attempt-scoped.

## Validation

- Exact physical training/evaluation and signed-installed lifecycle passed.
- The aggregate exit contains 24 true checks, including complete signed-install
  removal.
- Ruff, focused strict typing, conversion/schema round trips, release/lifecycle
  tests, and the final complete source suite are required before handoff close.

## Known limitations and risks

- This specialist is deliberately narrow: stable Python topological ordering,
  not general software engineering.
- One canary case is acceptable only because it invokes the full trusted
  deterministic test bundle; future specialists need capability-specific suites.
- Conversion workspaces are large; later factory retention policy should remove
  unneeded successful intermediates after digest/audit retention.
- Ollama's API is expected to be stable but not strictly versioned; contract
  tests and installed qualification remain required on upgrades.

## Recommended next entry point

Begin Phase 23.1 with the clean base and full workstation profile matrix, while
also retesting the user's VS Code/browser application-weaving flow from the
fresh installed release. Phase 21.7 remains separately blocked on a second
physical Linux machine.
