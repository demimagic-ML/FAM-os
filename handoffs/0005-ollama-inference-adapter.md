# Handoff 0005: Ollama inference adapter

**Date:** 2026-07-16  
**Plan step:** Phase 1.6  
**Status:** Complete  
**Previous handoff:** `0004-linux-hardware-discovery.md`

## Objective

Replace the three prototype-specific Ollama HTTP clients with one small, testable adapter behind the provider-neutral `InferenceRuntime` port while preserving the load, token, timing, model-residency, and unload behavior proven by the RNF experiments.

## Scope completed

- Added one Ollama runtime adapter for chat inference, loaded-model inspection, and explicit model unloading.
- Split provider work into settings, transport, payload construction, response conversion, errors, and runtime composition rather than creating a single runtime module with mixed responsibilities.
- Made the JSON transport injectable so adapter behavior can be tested without a running Ollama service.
- Kept prompts, expert selection, routing, escalation, reporting, and orchestration outside the adapter.
- Added `temperature` and optional `seed` to `InferenceRequest` so reproducible prototype behavior can be expressed through the provider-neutral port.
- Added optional accelerator-memory and context-token facts to `LoadedModel` so `/api/ps` information is not discarded.
- Converted Ollama nanosecond timing values into the existing seconds-based `InferenceMetrics` contract.
- Added synthetic, non-sensitive chat and process-list fixtures plus 14 focused tests, increasing the FAM_OS suite from 24 to 38 tests.
- Exercised the adapter against the live local Ollama service with `granite3.3:2b`, verified a non-empty response and metrics, and explicitly unloaded the model afterward.

## Explicitly not completed

- Streaming inference, embeddings, multimodal inputs, tool calls, authentication, and exposed reasoning are outside Phase 1.
- No route prompts, expert policy, escalation logic, or orchestration were moved from the parent RNF prototype.
- No systemd unit, service lifecycle, cgroup, pressure, or admission-control behavior was added; Phase 1.7 is next.
- The parent `rnf/` prototype was not modified and still contains its experimental clients as read-only reference implementations.
- No external API, CLI, desktop UI, application bridge, or FAM Shell integration was added.

## Architecture and decisions

ADR 0005 establishes one provider-neutral `InferenceRuntime` implementation per inference provider. Ollama-specific URLs, payload keys, response shapes, and nanosecond timing conversion remain inside `adapters/ollama`.

`OllamaRuntime` owns the provider interaction only. Callers own prompt construction and policy. `OllamaSettings` makes the base URL and timeout explicit. `JsonTransport` separates HTTP mechanics from runtime semantics, while payload and response conversion stay pure and fixture-testable.

The adapter sends `think: false` because the current Phase 1 contract exposes final response content rather than a reasoning stream. That choice is provider-local and can evolve when the public inference contract deliberately supports additional output channels.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/ports/inference.py` | Additive request controls and loaded-model resource facts |
| `src/fam_os/adapters/ollama/settings.py` | Validated base URL and timeout settings |
| `src/fam_os/adapters/ollama/transport.py` | Injectable JSON transport and standard-library HTTP implementation |
| `src/fam_os/adapters/ollama/payloads.py` | Pure chat and unload payload construction |
| `src/fam_os/adapters/ollama/responses.py` | Typed chat, metric, and loaded-model response conversion |
| `src/fam_os/adapters/ollama/runtime.py` | `InferenceRuntime` implementation over the transport boundary |
| `src/fam_os/adapters/ollama/errors.py` | Provider transport and protocol errors |
| `src/fam_os/adapters/ollama/__init__.py` | Public Ollama adapter exports |
| `src/fam_os/adapters/ollama/README.md` | Component ownership and exclusions |
| `tests/fixtures/ollama/` | Synthetic Ollama chat and process-list responses |
| `tests/unit/test_ollama_payloads.py` | Payload mapping and optional-field tests |
| `tests/unit/test_ollama_responses.py` | Response, metric, and protocol validation tests |
| `tests/unit/test_ollama_runtime.py` | Fake-transport runtime behavior tests |
| `tests/unit/test_ollama_transport.py` | HTTP transport success and failure tests |
| `tests/unit/test_inference_port.py` | Additive contract validation tests |
| `tests/hardware/ollama_runtime_smoke.py` | Opt-in live Ollama adapter smoke test |
| `docs/decisions/0005-ollama-inference-adapter.md` | Adapter-boundary ADR |
| `README.md`, `MASTER_PLAN.md`, component READMEs | Current status, evidence, ownership, and next step |

## Public interfaces

- `OllamaSettings`
- `OllamaRuntime`
- `JsonTransport`
- `UrllibJsonTransport`
- `OllamaError`
- `OllamaTransportError`
- `OllamaProtocolError`
- `InferenceRequest.temperature`
- `InferenceRequest.seed`
- `LoadedModel.accelerator_bytes`
- `LoadedModel.context_tokens`

These remain source-level Python interfaces. Phase 2 will define external serialization and compatibility policy.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 38 tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
FAM_OLLAMA_SMOKE_MODEL=granite3.3:2b PYTHONPATH=src python3 -m unittest tests.hardware.ollama_runtime_smoke -v
```

Result: 1 live adapter smoke test passed in 0.732 seconds. The response was non-empty and the test explicitly unloaded the model.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent RNF tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

The codebase knowledge graph was refreshed in fast mode and contained all nine queried Ollama settings, transport, conversion, runtime, and test symbols. Graph-augmented searches confirmed that `urllib` is confined to `adapters/ollama/transport.py`, Ollama `/api/` paths are confined to `adapters/ollama/runtime.py`, and `FAM_OS/src` imports no parent `rnf` modules.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 133 files indexed, 21 artifacts written, verification clean.

## Evidence and artifacts

The live Granite inference returned this non-sensitive adapter telemetry:

| Fact | Result |
|---|---:|
| Model | `granite3.3:2b` |
| Wall time | 0.651 seconds |
| Model load time | 0.581 seconds |
| Prompt tokens | 47 |
| Output tokens | 3 |
| Generation rate | 261.9 tokens/second |
| Non-empty final content | Yes |

After explicit unload, `/api/ps` contained only the pre-existing `nomic-embed-text:latest` model. Granite was no longer resident.

## Known limitations and risks

- The adapter currently performs non-streaming chat requests only.
- The transport supports JSON object request and response bodies, not streaming event frames.
- `think: false` intentionally omits a separate reasoning channel under the current contract.
- Ollama error responses are reported at the transport/protocol boundary but do not yet share a cross-provider structured error taxonomy.
- `loaded_models()` reflects Ollama's process list and does not represent a complete admission-control view of host or cgroup pressure.
- The adapter can request a context size but does not decide whether that size is safe for the machine; the future scheduler owns that policy.
- No retry policy is embedded in the transport. A future service layer must decide when retrying is safe.

## Operational notes

The only live state change was temporarily loading `granite3.3:2b` for the opt-in smoke test. The test and the additional telemetry check both explicitly unloaded it. No model was downloaded, no service was installed or restarted, and no configuration or device permission changed.

## Recommended next entry point

Begin Phase 1.7. Add small Linux systemd and cgroup adapters behind provider-neutral service and resource-control ports. Start with read-only discovery and fake-driven tests, then add explicit lifecycle operations with bounded commands. Keep inference, scheduling policy, service supervision, and resource enforcement as separate components.
