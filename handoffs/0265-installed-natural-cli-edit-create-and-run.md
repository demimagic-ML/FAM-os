# Handoff 0265: Installed natural CLI edit, create, and run

**Date:** 2026-07-19
**Plan step:** Phase 30.1 installed natural engineering lifecycle
**Status:** Partial (`installed_tested`; two live CLI scenarios passed)
**Previous handoff:** `0264-generated-workspace-links-pruned.md`

## Objective

Exercise the installed same-owner CLI with ordinary natural-language requests,
not direct APIs or mocked clients, and prove real repository edits, new code and
test creation, sandboxed execution, exact approvals, post-apply verification,
and local Git delivery.

## Scope completed

- Corrected the installed Bubblewrap/AppArmor/systemd boundary so real Python
  and Node toolchains execute under explicit layered enforcement.
- Passed the previously failing positive/negative polyglot sandbox integration.
- Bounded candidate prompts and outputs, propagated real sanitized verifier
  diagnostics into repair, and normalized the one safe repair case where a
  model re-emits creation of a file that now exists in its candidate.
- Staged exact approved paths even when repository ignore rules cover governed
  generated documents.
- Allowed only append-only Shell plan growth and visible terminal failures.
- Built and installed signed release
  `fam-os-natural-engineering-20260719-10` and activated only
  `fam-os-natural-signed-10.service` on port 8877.
- Through installed `fam-shell`, edited a disposable B2B checkout, ran signed
  verification, applied the exact checkpoint, reverified, and created clean
  commit `16b056c48747106f225c15ce30f6beed5a121931`.
- Through installed `fam-shell`, created `src/slugify.js` and
  `test/slugify.test.js`, ran the real Node verifier, applied and reverified the
  exact checkpoint, and created clean commit
  `9bee4886e1f033d26a96e2753feae7d94100b48f`.
- Declined each optional rollback and received a terminal verified receipt with
  the rollback step retained as denied.
- Independently reran `npm test` in the resulting owner checkout; all tests
  passed.

## Explicitly not completed

- The live release did not intentionally induce and successfully repair or
  escalate a failing candidate.
- No remote was authorized, so the separate push/draft-PR ceremony was not run.
- The complete Phase 30 exit matrix for refactoring, migration, UI redesign,
  rollback execution, and PR delivery remains open.
- Phase 31 both-profile qualification, soak, and human review remain open.

## Architecture and decisions

ADR 0228 assigns installed sandbox enforcement explicitly across AppArmor,
Bubblewrap, systemd cgroups, and subprocess rlimits. ADR 0229 permits only
append-only Shell lifecycle growth while preserving immutable existing plan
identity and visible terminal failure results.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/bubblewrap/engineering.py` | Explicit profiled collected sandbox scope |
| `src/fam_os/adapters/bubblewrap/process.py` | Tell rlimits when cgroup memory is authoritative |
| `src/fam_os/adapters/bubblewrap/rlimits.py` | Avoid conflicting address-space enforcement |
| `src/fam_os/product/candidate_engineering_api.py` | Measured Node process ceiling |
| `src/fam_os/core/engineering/candidate_generation_service.py` | Bounded generation and safe repair normalization |
| `src/fam_os/product/natural_engineering_repair.py` | Sanitized real diagnostic feedback |
| `src/fam_os/adapters/git/local.py` | Exact forced staging of approved ignored artifacts |
| `src/fam_os/shell/state.py` | Append-only lifecycle plan projection |
| `src/fam_os/adapters/shell/natural_engineering.py` | Retained denied rollback terminal step |
| `tests/unit/test_candidate_generation_service.py` | Generation and repair regressions |
| `tests/unit/test_engineering_execution.py` | Explicit sandbox command regression |
| `tests/unit/test_natural_engineering_execution.py` | Diagnostic and Node-bound regressions |
| `tests/unit/test_sandbox_process_capture.py` | Layered memory-limit regression |
| `tests/unit/test_git_delivery.py` | Exact ignored-path delivery regression |
| `tests/unit/test_fam_shell.py` | Append-only and terminal-failure reducer regressions |
| `docs/decisions/0228-installed-engineering-sandboxes-use-explicit-layered-enforcement.md` | Sandbox decision |
| `docs/decisions/0229-shell-lifecycle-plans-grow-append-only.md` | Shell projection decision |
| `artifacts/product/phase30/natural-cli-acceptance-20260719-01/evidence.json` | Machine-readable live evidence |

## Public interfaces

No wire schema changed. Shell snapshot semantics now permit an appended
optional lifecycle step while retaining immutable existing step identity. The
installed CLI commands remain plain natural text, `/context add file`,
`/approve`, and `/deny`.

## Validation

```bash
PYTHONPATH=src python3 -m unittest -v \
  tests.unit.test_candidate_generation_service \
  tests.unit.test_natural_engineering_execution \
  tests.unit.test_engineering_execution \
  tests.unit.test_sandbox_process_capture \
  tests.unit.test_git_delivery \
  tests.unit.test_fam_shell \
  tests.unit.test_fam_shell_natural_engineering \
  tests.integration.test_polyglot_engineering_sandbox
```

Result: 58 tests passed in 37.528 seconds.

```bash
PYTHONPATH=src python3 -m unittest discover -v -s tests/architecture
```

Result: all 41 architecture tests passed in 0.883 seconds.

```bash
PYTHONPATH=src python3 -m unittest -v \
  tests.security.test_engineering_adversarial \
  tests.unit.test_candidate_workspace
```

Result: all 11 adversarial and transactional candidate tests passed in 0.259
seconds.

```bash
cd /tmp/fam-os-code-cli10-H0eNYq && npm test
```

Result: Node TAP passed 1 test, 0 failures, exit code 0. Both CLI-produced
owner checkouts were clean after their FAM commits. `git diff --check` passed.

## Evidence and artifacts

- `artifacts/product/phase30/natural-cli-acceptance-20260719-01/evidence.json`
- Larry focused-test log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T17-43-51-901Z.log`
- Larry architecture log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T17-44-44-878Z.log`
- Larry adversarial/transaction log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T17-47-38-361Z.log`
- ADRs 0228 and 0229

## Known limitations and risks

- The selected 7B model produced functionally correct code and passing tests,
  but the generated test suite grouped four assertions in one test and did not
  name each requested case independently. Independent review of generated test
  quality remains necessary.
- The `/tmp` acceptance repositories are disposable; the evidence artifact
  preserves their commit, tree, file digests, and receipt identities.
- The original B2B worktree had pre-existing owner changes and was never used
  as an apply target.

## Operational notes

`fam-os-natural-signed-10.service` is active on port 8877 with runtime root
`/run/user/1000/fam-os-natural-signed-10`, durable state root
`/home/demimagic/.local/share/fam-os-natural-signed`, and model
`qwen2.5-coder:7b`. The older port-8765 service was not changed.

## Recommended next entry point

Advance Phase 30.1 with one installed CLI fixture that deliberately requires a
bounded repair or escalation, then run the separately approved publication
path against a disposable local bare remote. Start from
`src/fam_os/product/natural_engineering_execution.py`,
`src/fam_os/product/natural_engineering_repair.py`, and
`src/fam_os/adapters/shell/natural_engineering.py`.
