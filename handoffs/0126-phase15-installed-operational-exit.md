# Handoff 0126: Phase 15 installed operational exit

**Date:** 2026-07-16  
**Plan step:** Phase 15.7 and Master Plan operational exit  
**Status:** Complete  
**Previous handoff:** `0125-installed-service-operational-acceptance.md`

## Objective

Close the Master Plan only after proving the installed product actually runs.

## Scope completed

- Fresh release installation and systemd unit verification.
- Installed `fam-service` startup and clean SIGTERM shutdown.
- Installed `fam-shell` request through Core, Ollama, and `qwen3:1.7b`.
- GPU residency measured at 2,235,280,915 bytes.
- Console HTML and all six authenticated state sections loaded.
- Managed damage detected, repaired, and completely removed.
- Six real Shell/Console cycles passed a 60-second operational soak.
- Fresh virtual-environment wheel install executed all four CLI entry points.
- Full 842-test, 166-schema, whole-tree lint, and focused typing gates passed.

## Evidence and artifacts

- `artifacts/product/phase15/installed-operational-acceptance.json`
- `artifacts/product/phase15/operational-service-soak.json`
- `artifacts/product/phase15/phase15-exit.json`
- `docs/decisions/0110-master-plan-completion-requires-installed-operation.md`

## Known limitations and risks

- General local chat is deliberately unverified and has no application authority.
  Application actions still require their existing capability, approval, audit,
  postcondition, and verification workflows.
- A third-party human penetration test has not occurred.

## Recommended next entry point

Install into the owner's final prefix, link and enable the generated systemd user
unit, then use `fam-shell` for local chat and the loopback Console for visibility.
