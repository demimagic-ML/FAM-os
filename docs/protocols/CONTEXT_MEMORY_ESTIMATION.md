# Context-memory estimation

## Purpose

`fam.scheduler.context-memory/v1alpha1` separates per-request context memory
from immutable model residency. This distinction is required before admission,
offload, or eviction can add model weights and request growth without counting
the same bytes twice.

The contract family has three strict roots:

- `fam.scheduler.context-profile/v1alpha1`: model architecture and policy bounds;
- `fam.scheduler.context-reservation/v1alpha1`: input/output token upper bounds
  and concurrent sequence count;
- `fam.scheduler.context-estimate/v1alpha1`: auditable memory components and
  safety margin.

Every estimate asserts `model_resident_bytes_excluded=true`. A later placement
step must add a weight-only residency source. Historical Ollama `size` readings
may include runtime/context allocation and must not automatically be added as if
they were weight-only.

## Autoregressive strategy

For a transformer with grouped-query attention, the estimator reserves separate
prompt and output KV components:

```text
key bytes/token   = layers * KV heads * key dimension * scalar bytes
value bytes/token = layers * KV heads * value dimension * scalar bytes
prompt KV         = input upper bound * (key + value) * sequences
growth KV         = output reservation * (key + value) * sequences
```

The profile records scalar width as a policy assumption because runtime KV
quantization is deployment configuration. The reference policy uses two bytes,
which is conservative for q8/q4 caches and matches an f16 cache. Sliding-window
discounts are not applied unless a later calibrated profile proves the runtime's
layer pattern. This deliberately produces a high bound for Gemma 4, whose local
metadata omits KV-head count and window pattern.

## Encoder strategy

Embedding encoders do not reserve autoregressive output KV. Their conservative
peak uses three token/embedding buffers plus a full attention-score matrix:

```text
hidden buffers = tokens * embedding width * scalar bytes * 3 * sequences
attention peak = attention heads * tokens^2 * scalar bytes * sequences
```

The attention workspace is a peak reusable layer workspace, not a sum across
layers. The quadratic term prevents long encoder inputs from being mistaken for
linear KV growth.

## Shared components

Both strategies add a fixed runtime-overhead bound, per-sequence workspace, and
an integer ceiling safety margin. The reference observation policy uses 256 MiB
fixed overhead, 64 MiB per sequence, and 25 percent margin. These are declared
conservative policy bounds, not empirical calibration claims; their provenance
is retained in `assumption_codes`.

Reservations exceeding the package context ceiling fail. Encoder reservations
with output tokens fail. Profile mismatches, absent dimensions, invalid metadata,
and nonpositive sizes fail closed.

## Ollama adapter

`OllamaContextProfileObserver` calls local `/api/show` and maps architecture,
layer count, embedding width, attention heads, KV heads, key/value dimensions,
and native context capacity into the provider-neutral profile. Missing KV heads
fall back to all attention heads. Missing key/value dimensions are derived only
when embedding width divides attention heads exactly. Each fallback is retained
as an assumption.

## Reference evidence

`artifacts/scheduler/phase7.2/reference-context-estimates/` contains strict
profiles, reservations, and estimates for Llama 3.2 3B, Qwen 2.5 Coder 7B,
Nomic Embed, Laguna XS.2, and Gemma 4. The capture loads no model and changes no
runtime state; it observes already downloaded model metadata. Exact model refs
and package context ceilings are integration-tested against current manifests
and runtime bindings.

At 4,096 reserved input plus 1,024 output tokens (2,048 input and no output for
Nomic), the context-only totals are:

| Expert | Strategy | Context bytes |
|---|---:|---:|
| Llama 3.2 3B | autoregressive KV | 1,153,433,600 |
| Qwen 2.5 Coder 7B | autoregressive KV | 786,432,000 |
| Nomic Embed | encoder activation | 557,056,000 |
| Laguna XS.2 | autoregressive KV | 1,468,006,400 |
| Gemma 4 | conservative autoregressive KV | 6,710,886,400 |

These numbers are admission bounds under the recorded assumptions, not measured
resident deltas or performance comparisons.
