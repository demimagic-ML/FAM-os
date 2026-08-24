# ADR 0229: Shell lifecycle plans grow append-only

Status: Accepted

## Context

The installed Shell correctly received a verified local-commit outcome, but its
fail-closed snapshot reducer rejected the optional rollback step because the
step was not present in the initial three-step plan. The user therefore saw a
generic safety error even though Core had applied, reverified, and committed
the approved changes. The same reducer hid a durable terminal engineering
failure when its projection intentionally contained no active plan.

## Decision

An active Shell plan may append new, separately authorized lifecycle steps.
Every previously projected step must remain an exact ordered prefix with the
same step ID, kind, and description. Existing steps cannot be removed,
reordered, or rewritten. Step states may advance through the existing snapshot
contract.

A terminal failure may contain no projected steps because it exposes no new
authority and carries a typed failed result. When an owner declines the
optional post-commit rollback, the terminal projection retains the rollback
step and marks it denied instead of removing it.

## Consequences

- Optional rollback and publication checkpoints can be displayed after the
  ordinary lifecycle without weakening plan identity.
- Terminal engineering failures remain visible rather than becoming a generic
  client error.
- A server still cannot replace or shrink an active authority-bearing plan.
- The Shell remains a presentation client; Core continues to own authority,
  effects, verification, and receipts.

## Alternatives considered

- Disable stable-plan validation: rejected because a compromised or defective
  server could rewrite the user-visible plan after approval.
- Put every optional step in every initial plan: rejected because it presents
  irrelevant authorities before intent and policy select them.
- Suppress rollback after commit: rejected because it hides an existing safe,
  separately approved recovery action.

## Evidence

- `src/fam_os/shell/state.py`
- `src/fam_os/adapters/shell/natural_engineering.py`
- `tests/unit/test_fam_shell.py`
- `artifacts/product/phase30/natural-cli-acceptance-20260719-01/evidence.json`
