# ADR 0145: Conversion sandbox uses explicit ephemeral identity and caches

Status: Accepted

## Context

Qwen3 ships a fast-tokenizer JSON rather than `tokenizer.model`. The pinned
llama.cpp converter correctly falls back to Transformers for that vocabulary.
Importing Transformers reaches Torch cache initialization. Inside the
network-denied Bubblewrap namespace, the host UID intentionally has no passwd
entry and `HOME` is intentionally unusable, so implicit username and cache
discovery failed after base-weight conversion.

## Decision

The conversion sandbox declares the non-authoritative process identity
`fam-conversion` through `USER` and `LOGNAME`. All mutable caches and temporary
files are explicitly routed to the sandbox's private `/tmp`: XDG, Hugging Face,
Torch, TorchInductor, and `TMPDIR`. The host home, passwd database, and network
remain unavailable.

## Consequences

- The pinned converter can use the Qwen fast tokenizer through its supported
  Transformers fallback.
- No conversion cache or downloaded content can persist outside the sandbox.
- Username discovery does not depend on host account files.
- Offline flags and read-only model, adapter, environment, and llama.cpp mounts
  remain unchanged.

## Alternatives considered

- Mounting `/etc/passwd` was rejected because the worker does not need host
  account data.
- Giving the worker the user's real home was rejected because it would expose
  unrelated files and mutable caches.
- Adding a synthetic `tokenizer.model` was rejected because it would fabricate
  model input and change the pinned base artifact.

## Evidence

- `src/fam_os/adapters/training/isolated_conversion_command.py`
- `tests/unit/test_factory_conversion_isolation.py`
- Physical attempt 05 stderr under the canonical Phase 22 training artifact
