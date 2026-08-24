# Handoff 0240: Separately approved natural Git publication

**Date:** 2026-07-19  
**Plan step:** Phase 29.3--29.6 and Phase 30.1, 30.4, 30.5, 30.9  
**Status:** Partial  
**Previous handoff:** `0239-history-preserving-natural-rollback.md`

## Objective

Connect optional push and draft-PR delivery to the natural-language master
engineering lifecycle without inheriting edit authority or exposing secrets.

## Scope completed

- Derive publication from the FAM commit and provider remote observation.
- Persist encrypted proposal, intent, decline, recovery, and receipt state.
- Activate a separate short-lived task-scoped `publish + secret_use` grant.
- Consume one exact approval, push a new feature ref, verify the provider
  receipt, and reach terminal completion.
- Expose the full proposal through natural Console, Shell, and typed Shell Unix
  transport.
- Reject protected/existing refs, unsafe refs, untrusted broker sockets,
  replay, and restart reuse.

## Explicitly not completed

- Signed build, installation, or live-service promotion of this source change.
- Automatic local feature-branch creation from a protected current branch.
- Existing-ref reconciliation, advanced Git, multi-repository publication, or
  uncertain-effect reconciliation.
- Remaining Phase 27, Phase 30.6--30.8, and Phase 31 gates.

## Architecture and decisions

ADR 0206 makes publication a derived second ceremony. Local observation hashes
the remote URL before it crosses Core. The broker observes and mutates through
typed credential-opaque documents. Proposal persistence and single-use
consumption are separate so restart cannot reuse a final decision.

Publication product orchestration lives in
`product/git_publication_api.py` and
`product/natural_engineering_publication.py`, separate from candidate and model
generation modules.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/git_publication_proposal.py` | Local/remote observations, proposal, digest, and derived approval |
| `src/fam_os/core/engineering/git_service.py` | Preparation, approval intent, effect, and recovery gate |
| `src/fam_os/adapters/git/local.py` | Clean local commit/ref/diff and secret-free URL digest |
| `src/fam_os/adapters/git/unix_publication.py` | Typed broker and socket trust checks |
| `src/fam_os/adapters/sqlite/git_publication_proposal.py` | Encrypted restart-safe proposal state |
| `src/fam_os/product/git_publication_api.py` | Owner-scoped publication facade |
| `src/fam_os/product/natural_engineering_publication.py` | Natural publication ceremony |
| `src/fam_os/product/service.py` | Installed configuration and composition |
| `src/fam_os/console/natural_engineering_routes.py` | Publication decision route |
| `src/fam_os/console/static/natural_engineering.js` | Complete publication preview UI |
| `src/fam_os/shell/wire.py` | Typed publication Unix request |
| `src/fam_os/adapters/shell/natural_engineering.py` | Equivalent Shell checkpoint |

## Public interfaces

- Four new `fam.core.git-*` observation/proposal schemas.
- Console `POST .../proposals/{id}/publication-decision`.
- Shell `engineering_publication` and `engineering.git.publish`.
- `FAM_GIT_PUBLICATION_BROKER_SOCKET`, `FAM_GIT_PUBLICATION_REMOTE`, and
  `FAM_GIT_PUBLICATION_CREDENTIAL_REF` with matching CLI flags.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.integration.test_natural_engineering_publication \
  tests.unit.test_git_publication_proposal_store \
  tests.unit.test_fam_shell_natural_engineering \
  tests.integration.test_console_natural_engineering \
  tests.unit.test_product_natural_engineering_api \
  tests.integration.test_natural_engineering_checkpoint \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_unix_git_publication_broker \
  tests.unit.test_git_delivery tests.integration.test_git_publication_exit \
  tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility
```

Result: 50 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: 405 schemas validated.

The complete source suite ran 1,765 tests: 15 failures, 6 errors, and 7 skips.
The focused publication suites are green. Direct diagnosis reports the required
`fam-os-userns` AppArmor profile unavailable, withholding the 15 verifier
assertions and five Shell workflow starts; the sixth error is the absent
optional `mcp` Python SDK. These prerequisites were not weakened or skipped.

## Evidence and artifacts

- Focused log: `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-37-02-255Z.log`
- Full log: `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T08-29-43-230Z.log`
- `docs/decisions/0206-natural-git-publication-requires-a-derived-separate-grant.md`

## Known limitations and risks

- Only a clean non-protected feature branch and remotely absent ref are allowed.
- Provider effect without receipt stops in `recovery_required`.
- The live service on `127.0.0.1:8765` and active release were not changed.

## Operational notes

Natural publication needs all three settings. The broker owns the credential;
FAM stores and displays only its opaque `secret.*` reference.

## Recommended next entry point

Build a signed candidate and directly install-test rollback plus publication
through Console and Shell. Then attach documentation, incident, review,
dependency/design, and deployment services to the same Phase 30.1 lifecycle.
