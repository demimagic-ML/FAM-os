# ADR 0230: Codex subscription is an effect-free engineering inference adapter

Status: Accepted

## Context

The local sub-30B engineering model repeatedly produced malformed or
hallucinated candidate plans even though FAM_OS already owned the repository
inspection, approval, sandbox, verification, apply, rollback, and Git
boundaries. The owner has an active ChatGPT-authenticated Codex installation
whose current model catalog includes `gpt-5.6-sol`.

ChatGPT authorization is owned by Codex. Copying its OAuth material into
FAM_OS, translating it into an OpenAI Platform API key, or calling an
undocumented endpoint would create an unsupported credential and billing
boundary. Giving a second coding agent direct write or command authority would
also bypass FAM Core's candidate and approval lifecycle.

## Decision

FAM_OS may optionally compose a Codex subscription runtime only for the
untrusted candidate-generation chat port. The default remains the local Ollama
runtime. The Codex runtime invokes the installed `codex exec` client as the
same owner and lets Codex manage its own ChatGPT authorization. FAM_OS never
reads, copies, logs, persists, refreshes, or translates Codex OAuth material.

Each generation is an ephemeral, effect-free inference call:

- repository evidence is bounded and supplied through private standard input;
- the prompt is never placed in process arguments;
- user configuration and repository instruction discovery are disabled;
- web search and approval prompts are disabled;
- a custom permission profile grants only Codex minimal runtime reads and the
  empty FAM-owned inference directory;
- the process receives no FAM application, modification, execution, Git, or
  publication capability;
- JSONL output is bounded and parsed as untrusted data; any Codex tool event is
  rejected even if the child process reports success;
- FAM Core remains the sole owner of plan validation, candidate edits,
  deterministic tool execution, changeset approval, apply, reverification,
  rollback, commit, and optional publication.

The local residency runtime contract is split from the chat-only inference
contract. Ollama continues to own local catalog, embeddings, prewarm, unload,
residency, and offline routing. A subscription-backed model is never presented
as resident local compute.

The CLI exposes explicit owner-selected configuration:
`--engineering-provider codex-subscription`, `--codex-executable`,
`--codex-model`, `--codex-reasoning-effort`, and
`--codex-timeout-seconds`. The Codex working directory must be exactly the
private `<runtime-root>/codex-inference` directory.

## Consequences

- Natural-language engineering can use the stronger subscription model while
  preserving FAM_OS authority, verification, and audit boundaries.
- Repository evidence selected for generation is transmitted to OpenAI under
  the owner's ChatGPT workspace and plan controls; this provider choice is not
  offline or local-only execution.
- ChatGPT plan limits and Codex availability can interrupt generation. FAM_OS
  then fails the candidate and performs no owner-workspace effect.
- The integration does not provide Platform API access and does not accept an
  OpenAI API key. API-key routing remains a separate, usage-billed design.
- `codex exec` creates one process per generation. A future persistent
  app-server adapter may improve latency but must preserve the same
  effect-free contract and FAM-owned lifecycle.

## Alternatives considered

- Reuse Codex OAuth against the Responses API: rejected because it is not a
  documented Platform API authorization mechanism and would expose managed
  subscription credentials to FAM_OS.
- Require an OpenAI API key: valid for a separate Platform integration, but
  rejected for this owner request because it does not use the ChatGPT
  subscription and has separate usage billing.
- Allow Codex to edit and run directly in the owner repository: rejected
  because it bypasses FAM candidate isolation, exact approvals, deterministic
  verification, rollback, and receipts.
- Replace Ollama globally: rejected because subscription inference has no
  local model residency, unload, prewarm, or embedding semantics.

## Evidence

- `src/fam_os/adapters/codex_subscription/`
- `src/fam_os/product/composition/engineering_inference.py`
- `src/fam_os/core/ports/inference.py`
- `tests/unit/test_codex_subscription_runtime.py`
- `tests/hardware/codex_subscription_smoke.py`
- `artifacts/product/phase30/codex-subscription-acceptance-20260719-01/evidence.json`
- OpenAI Codex authentication: <https://learn.chatgpt.com/docs/auth>
- OpenAI Codex app server: <https://learn.chatgpt.com/docs/app-server>
- OpenAI Codex permissions: <https://learn.chatgpt.com/docs/permissions>
