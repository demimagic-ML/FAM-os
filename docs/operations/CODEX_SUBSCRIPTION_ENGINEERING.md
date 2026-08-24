# Codex subscription engineering provider

This optional provider uses the owner's existing ChatGPT sign-in in the
official Codex client for FAM_OS candidate generation. It does not turn a
ChatGPT subscription into an OpenAI Platform API key. OpenAI documents the
ChatGPT and API-key login modes separately:
<https://learn.chatgpt.com/docs/auth>.

## Owner setup

Install the official Codex CLI, sign in interactively, and verify the owner
session:

```bash
codex login
codex login status
```

The expected status for this provider is `Logged in using ChatGPT`. FAM_OS does
not read or copy the resulting credential file; it launches the authenticated
Codex client as the same OS owner.

## Start FAM_OS

Use the signed installed launchers and an absolute Codex executable path:

```bash
/home/demimagic/.local/share/fam-os-natural-current/bin/fam-service \
  --state-root /home/demimagic/.local/share/fam-os-natural-signed \
  --runtime-root /run/user/1000/fam-os-natural-codex-13 \
  --external-ollama \
  --ollama-url http://127.0.0.1:11434 \
  --model qwen2.5-coder:7b \
  --engineering-provider codex-subscription \
  --codex-executable /home/demimagic/.npm-global/lib/node_modules/@openai/codex/bin/codex.js \
  --codex-model gpt-5.6-sol \
  --codex-reasoning-effort medium \
  --codex-timeout-seconds 600 \
  --console-port 8877 \
  --device-name "FAM natural engineering signed"
```

Do not type the base URL into a fresh browser session; that intentionally lacks
the bootstrap credential and returns 401. Launch the Console through the
installed owner command:

```bash
/home/demimagic/.local/share/fam-os-natural-current/bin/fam-os \
  --prefix /home/demimagic/.local/share/fam-os-natural-current \
  console \
  --runtime-root /run/user/1000/fam-os-natural-codex-13 \
  --port 8877
```

The launcher opens <http://127.0.0.1:8877> with a token in the URL fragment,
exchanges it for an HttpOnly session, and removes the fragment from browser
history. Select a local repository folder and enter an ordinary engineering
request. Modification requests still require one bounded grant approval and a
second exact changeset approval. Commit, rollback, and publication remain
separate FAM-owned lifecycle steps.

## Security and privacy boundary

FAM sends only its bounded repository evidence and task envelope to Codex.
The child is ephemeral, has web disabled, ignores user configuration and
repository rules, receives an empty FAM-owned working directory, and is denied
approval-driven tools. FAM rejects output containing tool activity and treats
all returned text as an untrusted candidate plan. OpenAI documents Codex's
permission controls at <https://learn.chatgpt.com/docs/permissions> and the
Codex-owned managed-auth boundary at <https://learn.chatgpt.com/docs/app-server>.

Choosing this provider transmits the bounded prompt and repository excerpts to
OpenAI under the owner's ChatGPT plan and workspace controls. Ollama remains
the local runtime for local model catalog and residency duties.

## Verification

```bash
FAM_RUN_CODEX_SUBSCRIPTION_SMOKE=1 PYTHONPATH=src \
  python3 -m unittest -v tests.hardware.codex_subscription_smoke

/home/demimagic/.local/share/fam-os-natural-current/bin/fam-shell \
  --socket /run/user/1000/fam-os-natural-codex-13/shell.sock \
  --timeout 120
```

Inside the Shell, use a URI context such as:

```text
/context add uri file:///absolute/path/to/repository my-project
Analyze this repository, identify the highest-value safe improvement, implement it, run the relevant tests, show the exact changeset, apply it, reverify, and create a local commit. Do not publish.
```

Approve the bounded grant, inspect and approve the exact changeset, then deny
the optional rollback if the verified commit should be kept.
