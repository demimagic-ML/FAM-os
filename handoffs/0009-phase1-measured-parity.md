# Handoff 0009: Phase 1 measured parity

**Date:** 2026-07-16  
**Plan step:** Phase 1.10  
**Status:** Complete  
**Previous handoff:** `0008-verified-code-orchestration.md`

## Objective

Reproduce the parent RNF tests and measured routing, constrained activation, fresh-service residency, and verified escalation workflows from FAM_OS-owned modules and entry points, preserve raw evidence, compare required outcomes, and expose any migration drift before the parent prototype is marked read-only.

## Scope completed

- Added typed four-route evaluation cases, per-case results, route scores, and model summaries.
- Shared the production model-routing request builder between `ModelTaskRouter` and benchmark evaluation.
- Added a non-releasing `ExpertActivationProbe` that records routing, placement, loaded-model, candidate, and inference evidence without creating a successful `TaskResult` from unverified output.
- Added typed readers for the frozen parent JSON fixtures; these are parity-only compatibility readers, not the Phase 2 configuration system.
- Added an explicit in-memory expert catalog and placement planner for benchmark composition only.
- Added a fresh CPU-only user-systemd Ollama service composition using migrated lifecycle and cgroup adapters.
- Added small routing, activation, three-policy comparison, verified-escalation, report-writing, serialization, parity-check, and overall-report entry points.
- Added eight focused unit tests for routing evaluation, activation probing, typed fixture parsing, static policy validation, and parity relations.
- Reproduced all 10 parent RNF tests and increased the FAM_OS suite from 93 to 103 passing tests.
- Re-ran Linux hardware parity, Ollama lifecycle, systemd/cgroup, Bubblewrap, and Python verifier live checks.
- Reproduced the exact 23/24 Granite routing result and the same `kernel-03` miss.
- Reproduced all three 2K CPU-only residency policies in fresh 16 GiB/no-swap services.
- Reproduced verified economical failure, bounded repair failure, 14B escalation pass, and passing-candidate-only release.
- Found and preserved an asynchronous Ollama unload race during the first policy comparison.
- Changed `InferenceRuntime.unload` semantics to confirmed logical absence and implemented a bounded `/api/ps` barrier in the Ollama adapter.
- Added immediate, delayed, and unconfirmed unload regression coverage.
- Produced a passing canonical Phase 1 machine report and a human parity report.
- Added ADR 0009 for the confirmed-eviction runtime boundary.

## Explicitly not completed

- The parent RNF implementation is not yet marked read-only; Phase 1.11 is the next and final migration step.
- No production expert registry or placement algorithm was added.
- No versioned public configuration or report schema was added; historical fixture parsing and JSON artifacts are benchmark-only.
- No user-facing CLI, FAM Shell, local API, persistence service, or production telemetry exporter was added.
- No new model was downloaded and no GPU or NPU acceleration policy was introduced.
- No claim is made that logical model absence immediately reclaims every allocator or file-cache byte.
- The Phase 1 parity artifacts contain trusted benchmark prompts and raw generated candidates and must not be treated as client response formats.

## Architecture and decisions

ADR 0009 changes the runtime contract: `InferenceRuntime.unload(model_ref)` must return only when `loaded_models()` no longer reports the model, or raise within a bounded timeout. The scheduler therefore receives a real activation barrier instead of a fire-and-forget provider acknowledgement.

The first migrated policy comparison demonstrated why this matters. Ollama acknowledged Granite eviction, but the following loaded-model observation still contained Granite. The 14B load overlapped the delayed eviction and the supposed eviction policy peaked above the persistent policy. This failed run remains at `artifacts/parity/policy-parity-20260716-093229-742050.json`.

After the adapter enforced confirmed absence, the canonical policy report reproduced the intended relationship. This does not make `/api/ps` a memory authority: cgroup current, peak, pressure, swap, and OOM events remain required because logical model state and actual charged bytes are different facts.

`ExpertActivationProbe` is deliberately not a result-producing Core path. Its candidate is explicitly unverified measurement evidence. Verified user-visible content still flows only through `VerifiedCodeExecution` and `TaskResult`.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/routing/evaluation.py` | Typed routing cases, results, evaluation, and summaries |
| `src/fam_os/routing/parsing.py`, `inference.py` | Structured-response evidence and shared routing request construction |
| `src/fam_os/core/activation/` | Non-releasing route-and-activation measurement use case |
| `src/fam_os/core/ports/inference.py` | Confirmed-absence unload semantics |
| `src/fam_os/adapters/ollama/settings.py`, `runtime.py` | Bounded unload polling and completion failure |
| `tools/parity/historical_config.py` | Typed frozen-fixture compatibility readers |
| `tools/parity/cpu_service.py` | Fresh 16 GiB/no-swap CPU service composition |
| `tools/parity/static_policy.py` | Benchmark-only catalog and placement policy |
| `tools/parity/serialization.py`, `report_writer.py` | Stable benchmark artifact conversion and writing |
| `tools/parity/checks.py` | Explicit routing, resource, policy, and verification gates |
| `tools/run_routing_parity.py` | 24-case routing entry point |
| `tools/run_activation_parity.py` | One residency-policy entry point |
| `tools/run_policy_parity.py` | Three fresh-service comparison entry point |
| `tools/run_verified_parity.py` | FAM-owned verified escalation entry point |
| `tools/build_phase1_parity_report.py` | Overall migration parity assembly |
| `tests/unit/test_routing_evaluation.py` | Evaluation parsing, fallback, and summary tests |
| `tests/unit/test_activation_probe.py` | Non-releasing activation transition tests |
| `tests/unit/test_parity_tooling.py` | Fixture, static-policy, and comparison tests |
| `tests/unit/test_ollama_runtime.py` | Confirmed, delayed, and failed unload tests |
| `docs/decisions/0009-confirmed-runtime-eviction.md` | Runtime eviction barrier decision |
| `docs/migration/PHASE_1_PARITY_REPORT.md` | Human interpretation of canonical evidence |
| `docs/migration/PROTOTYPE_MIGRATION_MAP.md` | Phase 1.10 completion status |
| `README.md`, `MASTER_PLAN.md`, component READMEs | Status, ownership, evidence, and next step |
| `artifacts/parity/*.json` | Canonical and diagnostic raw measurements |

## Public interfaces

- `RoutingCase`
- `RoutingCaseResult`
- `RouteScore`
- `RoutingModelSummary`
- `parse_routing_cases(lines)`
- `evaluate_routing_model(runtime, settings, cases)`
- `summarize_routing_model(model_ref, results)`
- `parse_route_evidence(content, request)`
- `build_model_routing_request(settings, request)`
- `ActivationProbeStatus`
- `ActivationProbeOutcome`
- `ExpertActivationProbe`
- Confirmed `InferenceRuntime.unload(model_ref)` semantics
- `OllamaSettings.unload_timeout_seconds`
- `OllamaSettings.unload_poll_seconds`

The `tools/` fixture, service, policy, serializer, check, and runner interfaces are development surfaces, not production runtime APIs.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests
```

Result: 103 tests passed in 0.006 seconds, 0 failures.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests
```

Result: all 10 parent tests passed in 0.026 seconds, 0 failures.

Live checks passed:

- Linux profile parity: 1 test in 0.087 seconds.
- Ollama runtime lifecycle: 1 test in 1.969 seconds.
- User-systemd/cgroup lifecycle: 1 test in 0.059 seconds.
- Bubblewrap isolation, timeout, and output bounds: 3 tests in 0.132 seconds.
- Parent-versus-FAM Python verifier parity: 2 tests in 0.051 seconds.

```bash
PYTHONPATH=src:. python3 -m tools.run_routing_parity \
  --config ../configs/evaluation-cpu-16gb.json \
  --output-dir artifacts/parity
```

Result: 23/24 correct, 23/24 structured JSON, 2.103-second mean wall time, 22.98 tokens/second, 2,302,586,880-byte peak, zero swap, zero OOM kills.

```bash
PYTHONPATH=src:. python3 -m tools.run_policy_parity \
  --config ../configs/policy-persistent-14b.json \
  --config ../configs/policy-evict-14b.json \
  --config ../configs/policy-persistent-7b.json \
  --output-dir artifacts/parity
```

Result: all gates passed. Persistent 14B peaked at 13,093,113,856 bytes; confirmed-eviction 14B at 12,131,512,320 bytes; persistent 7B at 6,698,876,928 bytes. All used zero swap and accelerator memory with zero OOM kills. The 7B expert achieved 9.03 tokens/second versus 4.66 for persistent 14B.

```bash
PYTHONPATH=src:. python3 -m tools.run_verified_parity \
  --config ../configs/verified-toposort-cpu-16gb.json \
  --trusted-tests tests/fixtures/verification/stable_topological_sort_tests.py \
  --output-dir artifacts/parity
```

Result: `verified_after_escalation`; economical and repair attempts failed, 14B escalation passed in Bubblewrap, only the passing candidate was released, peak memory was 12,304,621,568 bytes, swap was zero, and OOM kills were zero.

```bash
PYTHONPATH=src:. python3 -m tools.build_phase1_parity_report \
  --routing artifacts/parity/routing-parity-20260716-094554-188044.json \
  --policy artifacts/parity/policy-parity-20260716-094449-098883.json \
  --verified artifacts/parity/verified-parity-20260716-094942-805211.json \
  --diagnostic artifacts/parity/policy-parity-20260716-093229-742050.json \
  --fam-tests 103 --parent-tests 10 --output-dir artifacts/parity
```

Result: `passed: true`; no failed gates.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tools tests
```

Result: completed successfully.

The codebase graph was refreshed with 2,298 nodes and 6,880 edges. It found the routing evaluation, activation probe, shared routing request builder, confirmed unload, and unload-wait method. Larry was refreshed with 251 files, 496 symbols, 34 changed artifacts, and a clean graph update.

All new implementation files remain below 204 lines. Responsibilities are split across evaluation, probe, composition, configuration compatibility, serialization, checks, and individual entry points.

## Evidence and artifacts

- `artifacts/parity/phase1-parity-20260716-095056-252893.json`
- `artifacts/parity/routing-parity-20260716-094554-188044.json`
- `artifacts/parity/policy-parity-20260716-094449-098883.json`
- `artifacts/parity/verified-parity-20260716-094942-805211.json`
- Diagnostic unload race: `artifacts/parity/policy-parity-20260716-093229-742050.json`
- `docs/migration/PHASE_1_PARITY_REPORT.md`
- `docs/decisions/0009-confirmed-runtime-eviction.md`

## Known limitations and risks

- The host has 64 GiB physical RAM; the 16 GiB target was enforced through a user-service cgroup rather than tested on a physically 16 GiB machine.
- Host swap is heavily occupied by unrelated processes, but every parity service had `MemorySwapMax=0` and reported zero service swap use.
- Confirmed logical absence does not guarantee immediate complete cgroup memory reclamation.
- Timing and peak memory vary across cold runs; raw artifacts must accompany conclusions.
- The benchmark compatibility readers accept frozen Phase 1 JSON rather than a versioned public schema.
- The activation probe records unverified candidate content and is not a user response path.
- Reports contain raw model output and are trusted local evidence only.
- Only Granite routing and Python code escalation were measured.
- The current local Ollama build is 0.30.11; future runtime changes require rerunning the measured gates.

## Operational notes

Each policy and verified run used a fresh `fam-parity-ollama.service` user unit on `127.0.0.1:11435`, CPU-only, with 16 GiB memory and zero swap. Every unit was stopped after its report; the service is inactive. The main Ollama service on `127.0.0.1:11434` remained available. No model was downloaded, removed, or modified.

## Recommended next entry point

Complete Phase 1.11. Add a scoped read-only policy marker for `rnf/`, update the parent README with the canonical FAM_OS replacement and parity evidence, and add an automated architecture test that rejects imports of parent implementation modules from `FAM_OS/src`. Re-index discovery after the marker is in place, run all FAM_OS and parent tests once more, then close Phase 1 with handoff 0010.
