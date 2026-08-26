# ADR 0233: Codex runs as a native agent inside the candidate

## Status

Accepted. Supersedes the engineering-execution portion of ADR 0230. The
effect-free `ChatInferenceRuntime` remains available for narrow text turns.

## Context

Treating the ChatGPT-authenticated Codex CLI as a text-only JSON generator
discarded the capabilities for which Codex was selected. Codex could neither
inspect nor change the candidate, and its native tool activity was rejected.

## Decision

With `--engineering-provider codex-subscription`:

- implementation runs with Codex `workspace-write` access rooted at FAM's
  isolated candidate;
- repository answers run read-only against the selected owner workspace;
- Codex can use native coding tools and the owner's development toolchain;
- user Codex configuration remains available for native-agent turns;
- real filesystem changes are replayed through FAM's candidate-edit service;
- interrupted changes are reconciled when possible;
- FAM independently verifies and applies the candidate;
- Codex does not stage, commit, publish, or mutate the owner workspace.

The default native turn budget is two hours with bounded JSONL output. The
legacy effect-free parser remains strict for inference-only calls.

## Consequences

Codex performs engineering rather than only describing operations, while FAM
retains recoverability and the candidate boundary. The integration still starts
one Codex process per native turn; durable app-server thread resumption remains
a future improvement.
