# Handoff 0266: ChatGPT-authenticated Codex engineering runtime

**Date:** 2026-07-19
**Plan step:** Phase 30.1 and 30.9 installed natural engineering composition
**Status:** Partial (`installed_tested`; provider and one real lifecycle passed)
**Previous handoff:** `0265-installed-natural-cli-edit-create-and-run.md`

## Objective

Let an owner explicitly select the stronger `gpt-5.6-sol` model available
through the owner's ChatGPT-authenticated Codex installation for natural-
language candidate generation, without giving Codex direct repository, command,
approval, Git, or publication authority and without copying managed OAuth
material into FAM_OS.

## Scope completed

- Added an optional `codex-subscription` engineering provider while retaining
  Ollama as the default and as the only local residency/catalog runtime.
- Split the chat-only inference contract from local model lifecycle methods so
  a cloud/subscription model is not falsely represented as locally resident.
- Added a bounded Codex adapter that sends the prompt by private standard
  input, uses an ephemeral ignored-config/ignored-rules session, disables web
  and approvals, confines filesystem reads to Codex minimum runtime files and
  an empty FAM-owned work directory, and rejects every model tool event.
- Added explicit CLI settings and fail-closed runtime-root validation.
- Passed a real ChatGPT-entitlement smoke against `gpt-5.6-sol` with no model
  tool activity.
- Built and installed signed release
  `fam-os-natural-engineering-20260719-12`, activated
  `fam-os-natural-codex-12.service`, and verified Console HTTP 200 on port 8877.
- Exercised the installed Console launcher; it opened the authenticated URL
  fragment, and both the session exchange and authenticated snapshot returned
  HTTP 200 without exposing the bootstrap token.
- Sent one ordinary natural-language task through the installed `fam-shell`.
  The task analyzed a disposable Python repository, added `multiply`, added
  positive/negative/zero tests, passed candidate verification, displayed the
  exact two-file changeset, applied only after the second owner approval,
  passed post-apply reverification, and created clean commit
  `43aea1e2afa9546bec4e2c2b4e10af43d12b184e`.
- Independently reran the four tests in the owner tree; all passed.
- Found and fixed a real lifecycle defect in the first installed run:
  verifier-generated `__pycache__` was treated as an unauthorized candidate
  edit and stopped a correct, already verified candidate before checkpoint.
  Candidate final-state scans now retain the owner baseline's non-authoritative
  cache exclusions, with regression coverage.

## Explicitly not completed

- The provider is not an OpenAI Platform API-key integration and does not turn
  a ChatGPT subscription into API credit.
- A persistent Codex app-server session was not composed; each generation uses
  one bounded `codex exec` process.
- No remote publication was authorized or exercised.
- The live repair/escalation scenario and the complete Phase 30 scenario matrix
  remain open.
- Phase 31 both-profile qualification, 24-hour soak, and independent human
  security review remain open.

## Architecture and decisions

ADR 0230 establishes Codex subscription access as an effect-free
`ChatInferenceRuntime` used only by `CandidateGenerationService`. Codex owns its
ChatGPT OAuth lifecycle. FAM_OS owns the input bounds, child-process policy,
output parser, plan validation, candidate workspace, deterministic tool runs,
approvals, apply, rollback, Git, and audit receipts. Any Codex tool event is a
generation failure, not an executable instruction.

The candidate scanner fix does not authorize build/cache output. It makes
owner-baseline and candidate-final scans consistently exclude known
non-authoritative cache directories produced by trusted verifiers.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/ports/inference.py` | Separate chat inference from local residency lifecycle |
| `src/fam_os/core/engineering/candidate_generation_service.py` | Accept the chat-only runtime contract |
| `src/fam_os/adapters/linux/bounded_command.py` | Bounded private standard-input support |
| `src/fam_os/adapters/codex_subscription/` | Settings, errors, JSONL parser, and effect-free Codex runtime |
| `src/fam_os/product/composition/engineering_inference.py` | Compose local or subscription engineering inference |
| `src/fam_os/product/service.py` | Wire the provider only into candidate generation |
| `src/fam_os/product/service_cli.py` | Add explicit Codex provider flags |
| `src/fam_os/adapters/filesystem/candidate_workspace.py` | Ignore verifier-created non-authoritative cache trees in final scans |
| `tests/unit/test_bounded_command_runner.py` | Private standard-input bound regression |
| `tests/unit/test_codex_subscription_runtime.py` | Command policy, parser, and tool-event denial tests |
| `tests/unit/test_engineering_inference_composition.py` | Provider-boundary tests |
| `tests/unit/test_product_service_cli.py` | CLI composition test |
| `tests/unit/test_product_service_startup_safety.py` | Work-root escape denial test |
| `tests/unit/test_candidate_workspace.py` | Verifier-cache changeset regression |
| `tests/hardware/codex_subscription_smoke.py` | Opt-in real entitlement/model smoke |
| `docs/operations/CODEX_SUBSCRIPTION_ENGINEERING.md` | Owner setup, launch, privacy, and test instructions |
| `docs/decisions/0230-codex-subscription-is-an-effect-free-engineering-inference-adapter.md` | Durable credential and authority decision |
| `artifacts/product/phase30/codex-subscription-acceptance-20260719-01/evidence.json` | Machine-readable installed evidence |

## Public interfaces

New `fam-service` options:

```text
--engineering-provider {ollama,codex-subscription}
--codex-executable PATH
--codex-model MODEL
--codex-reasoning-effort {low,medium,high,xhigh,max,ultra}
--codex-timeout-seconds SECONDS
```

New internal public port: `ChatInferenceRuntime.chat(...)`. Existing
`InferenceRuntime` extends this port with unload, prewarm, and residency
observation. No wire schema changed.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_bounded_command_runner \
  tests.unit.test_codex_subscription_runtime \
  tests.unit.test_engineering_inference_composition \
  tests.unit.test_product_service_cli \
  tests.unit.test_product_service_startup_safety \
  tests.unit.test_candidate_generation_service \
  tests.unit.test_natural_engineering_execution \
  tests.unit.test_candidate_workspace \
  tests.unit.test_candidate_changeset_service \
  tests.unit.test_fam_shell_natural_engineering \
  tests.unit.test_fam_shell \
  tests.integration.test_polyglot_engineering_sandbox

PYTHONPATH=src python3 -m unittest discover -s tests/architecture

FAM_RUN_CODEX_SUBSCRIPTION_SMOKE=1 PYTHONPATH=src \
  python3 -m unittest -v tests.hardware.codex_subscription_smoke

PYTHONPATH=src python3 -m compileall -q src tests
git diff --check
```

Results:

- focused/unit/polyglot: 76 passed, 0 failed;
- architecture: 41 passed, 0 failed;
- real ChatGPT-authenticated Codex smoke: 1 passed, 0 failed;
- real installed lifecycle: verified, two paths, two approval checkpoints,
  four candidate tests, four post-apply tests, clean local commit;
- independent owner-tree tests: 4 passed, 0 failed;
- compile and diff checks: passed.

## Evidence and artifacts

- `artifacts/product/phase30/codex-subscription-acceptance-20260719-01/evidence.json`
- signed release manifest SHA-256:
  `c35970fd1f49b9a8ff8a5d1c2d7d67d3ffe872e6526d55e5bc03062b6fa24897`
- signed wheel SHA-256:
  `e9bcd651c29925d57c16258b9a7efb3f62672e9288059060dd8a416877ed95a6`
- candidate evidence: `evidence-360296a5-e621-40de-95df-353dd8ea2a9a`
- post-apply evidence: `evidence-4821bb5e-b481-4bbb-a22d-fd90afeb499d`
- Git receipt: `git-local-receipt-db0c9b5940fe4c268b4dfaccdf761b70`

## Known limitations and risks

- Bounded repository evidence sent for generation leaves the local machine and
  is governed by the owner's ChatGPT plan/workspace controls.
- ChatGPT rate limits, entitlement changes, client changes, or network loss can
  fail generation. The current boundary fails before any owner effect.
- One-process-per-generation startup is slower than a persistent app-server.
- The provider currently depends on compatible documented Codex CLI flags and
  JSONL events; parser drift fails closed and requires a qualified update.
- Local Ollama still handles non-engineering local inference duties in this
  installed composition.

## Operational notes

- Active unit: `fam-os-natural-codex-12.service`.
- Browser Console: `http://127.0.0.1:8877`.
- Shell socket: `/run/user/1000/fam-os-natural-codex-12/shell.sock`.
- State root: `/home/demimagic/.local/share/fam-os-natural-signed`.
- Previous signed releases remain available to the atomic release manager for
  rollback. Release 10 is no longer active.
- The generated release private key is temporary build material and must not be
  retained after final evidence checks.

## Recommended next entry point

Continue Phase 30.1 with an installed deliberately failing candidate that must
repair successfully or escalate safely, then exercise the separately approved
publication path. Start with
`src/fam_os/product/natural_engineering_execution.py`,
`src/fam_os/product/natural_engineering_repair.py`, and the installed
acceptance pattern recorded in this handoff.
