# Native Codex engineering provider

FAM_OS can use the owner's existing ChatGPT login from the official Codex CLI
as its primary engineering agent. Codex inspects, edits, and tests FAM's
isolated candidate workspace with its native coding tools. FAM still owns the
durable task, candidate ledger, independent verification, approval, and final
application to the owner's workspace.

This is not an OpenAI Platform API-key integration. Repository evidence and
candidate content used by Codex are processed under the owner's ChatGPT plan
and workspace controls.

## Sign in

Install the official Codex CLI and authenticate it as the same OS user that
runs FAM:

```bash
codex login
codex login status
```

The expected status is `Logged in using ChatGPT`. FAM does not read, copy, or
translate OAuth material; it launches the authenticated Codex client.

## Start FAM with native Codex engineering

Run from the repository root and use paths appropriate for the current machine:

```bash
PYTHONPATH=src .venv/bin/python -m fam_os.product.service \
  --state-root "${XDG_DATA_HOME:-$HOME/.local/share}/fam-os" \
  --runtime-root "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/fam-os" \
  --external-ollama \
  --ollama-url http://127.0.0.1:11435 \
  --model qwen3.8:27b \
  --engineering-provider codex-subscription \
  --codex-executable "$(command -v codex)" \
  --codex-model gpt-5.6-sol \
  --codex-reasoning-effort high \
  --codex-timeout-seconds 7200 \
  --console-port 8775
```

Ollama remains available for local-model catalog and fallback duties. Native
Codex is used for repository questions and engineering execution.

## Execution lifecycle

1. FAM creates or restores the isolated candidate workspace.
2. Codex runs there with native file, search, shell, planning, and configured
   web/tool capabilities.
3. Codex implements, tests, diagnoses failures, and self-corrects.
4. FAM derives the actual tree changes, restores the pre-turn tree, and replays
   every effect through its authorized durable candidate-edit ledger.
5. Successful Codex commands are retained as execution evidence.
6. FAM independently checks completion before applying anything to the owner
   workspace.

Interrupted work is reconciled into the candidate ledger when possible, so a
durable goal can continue from preserved work rather than repeating confirmed
filesystem effects.

Codex is told not to stage, commit, or push. Codex owns engineering inside the
candidate; FAM owns acceptance and delivery.

## Verification

Unit verification does not consume an external model request:

```bash
PYTHONPATH=src .venv/bin/python -m unittest -v \
  tests.unit.test_codex_subscription_runtime \
  tests.unit.test_candidate_agent_tools \
  tests.unit.test_engineering_inference_composition \
  tests.unit.test_product_service_cli
```

The opt-in live smoke makes a real Codex request:

```bash
FAM_RUN_CODEX_SUBSCRIPTION_SMOKE=1 PYTHONPATH=src \
  .venv/bin/python -m unittest -v tests.hardware.codex_subscription_smoke
```
