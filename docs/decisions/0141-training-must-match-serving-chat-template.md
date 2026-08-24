# ADR 0141: Training must match the serving chat template

Status: Accepted

## Context

The first physical specialist series trained standard string `prompt` and
`completion` fields. Production evaluation rendered the same semantic prompt
through the pinned Qwen chat template with `enable_thinking=false`. The
candidate therefore learned raw text boundaries but was asked to infer after
Qwen user, assistant, and no-thinking control tokens. Increasing the dataset
from 1,000 to 5,000 examples did not remove the hard safety and evidence-honesty
failures. A separate non-held-out development probe also showed unnecessary
prose on an exact-output task and one unsupported success claim.

## Decision

The QLoRA worker accepts only the explicit
`qwen_chat_prompt_completion_v1` record format. It converts each sealed input
and completion into conversational user and assistant messages and attaches
`chat_template_kwargs={"enable_thinking": false}`. TRL applies the pinned
tokenizer chat template and completion-only loss. The worker also binds the
tokenizer EOS token into `SFTConfig`; for the approved Qwen3 revision this is
`<|im_end|>`.

The training environment digest continues to bind the exact worker script.
Changing the record format, chat-template behavior, tokenizer, or worker
therefore creates a new approval and a new physical experiment series. Earlier
raw-format adapters remain immutable non-promotable evidence. The first
comparison reruns the unchanged `diverse2500` data and fixed held-out suite so
the representation correction is the only intended training variable.

## Consequences

- Training and serving now share the same user-to-assistant token boundary.
- Completion loss excludes both the user prompt and Qwen's no-thinking prefix.
- Legacy raw-format job configs fail closed instead of silently producing a
  semantically incompatible adapter.
- Existing signed denials are preserved and are not reinterpreted.
- A matching template removes one known defect but does not weaken any
  promotion gate or guarantee that an adapter will pass.

## Alternatives considered

- Increasing to 10,000 repetitions was rejected because the 2,500 and 5,000
  results had already saturated while using the wrong representation.
- DPO was deferred because correcting supervised tokenization is a prerequisite;
  preference optimization would otherwise inherit the same mismatch.
- Prompt-only workarounds at evaluation time were rejected because installed
  inference must retain the model's approved chat protocol.

## Evidence

- `src/fam_os/adapters/training/qlora_worker.py`
- `src/fam_os/product/factory_training_workspace.py`
- `tests/unit/test_qlora_worker_records.py`
- `artifacts/training/phase22-stable-toposort-diverse2500-20260718-01/evidence.json`
- [TRL SFT Trainer](https://huggingface.co/docs/trl/en/sft_trainer)
