# Handoff 0235: Natural-language verified local delivery

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0234-durable-task-intent-and-active-preparation.md`

## Objective

Continue the active preparation path through model-generated candidate edits,
trusted verification, exact approval, transactional apply, independent
reverification, and replay-safe local Git delivery from natural-language
Console and Shell requests.

## Scope completed

- Added bounded, no-symlink, secret-filtered candidate source context.
- Added a strict generated-plan contract, bounded inference/repair parsing, and
  current-baseline binding to typed candidate operations.
- Persisted generation intent and validated plans before effects; installed
  composition owner-encrypts proposal and generation records and migrates prior
  plaintext rows with secure deletion.
- Selected verification recipes only from the installed signed catalog and
  required the full selected verifier set before candidate or post-apply stage
  advancement.
- Produced exact complete changeset previews, bound owner confirmation to their
  digest, applied transactionally, and reobserved/reverified the owner tree.
- Added intent-before-effect local Git delivery with exact-path staging,
  evidence-bound commits, and exact crash reconciliation.
- Routed selected-workspace natural language through the real Console and Shell
  product facade with separate grant and changeset checkpoints.
- Corrected device-certificate validity checks for the installed cryptography
  API while preserving timezone-aware validation.

## Explicitly not completed

- Signed installed-product qualification of this path.
- Loading the required root-owned `fam-os-userns` AppArmor profile; this host
  currently rejects Bubblewrap loopback namespace setup.
- Optional remote publication, active rollback controls, multi-repository work,
  and Phase 29.7/29.8 delivery.
- Installed documentation, incident, and independent-review orchestration.
- Phase 27.11--27.16 completion matrices, both independently enforced hardware
  profiles, 24-hour soak, and independent human security review.

## Architecture and decisions

ADR 0202 makes untrusted structured generation, trusted recipe selection,
aggregate verification, two owner checkpoints, encrypted pre-effect state, and
replay-safe local Git delivery architectural requirements.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/candidate_generation.py` | Strict generated plan contract and parser |
| `src/fam_os/core/engineering/candidate_generation_service.py` | Bounded inference and repair coordination |
| `src/fam_os/core/engineering/candidate_generation_binding.py` | Current-state and budget binding |
| `src/fam_os/core/engineering/local_git_delivery.py` | Replay-safe exact local commit lifecycle |
| `src/fam_os/product/natural_engineering_execution.py` | Candidate generation through checkpoint orchestration |
| `src/fam_os/product/natural_engineering_api.py` | Owner activation, apply, reverify, and commit facade |
| `src/fam_os/adapters/filesystem/candidate_context.py` | Bounded secret-filtered model context |
| `src/fam_os/adapters/sqlite/candidate_generation.py` | Durable encrypted generation state and migration |
| `src/fam_os/adapters/sqlite/natural_engineering.py` | Durable encrypted proposal state and migration |
| `src/fam_os/adapters/shell/natural_engineering.py` | Natural Shell task and approvals |
| `src/fam_os/console/static/natural_engineering.js` | Conversation-first natural engineering controls |
| `src/fam_os/fabric/certificate_validity.py` | Cryptography-version-compatible UTC validity policy |

## Public interfaces

Added generated candidate plan/context/record and local Git delivery schema
roots; natural proposal, activation, progress, changeset-decision, and decline
product operations; Console natural-engineering routes; and Shell projection of
the same two-checkpoint lifecycle.

## Validation

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_*engineering*.py'
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_fam_shell*.py'
PYTHONPATH=src python3 -m unittest \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_console_natural_engineering -v
PYTHONPATH=src python3 -m unittest discover -s tests/contract -p 'test_*.py'
PYTHONPATH=src python3 -m unittest discover -s tests/architecture -p 'test_*.py'
PYTHONPATH=src python3 -m unittest discover -s tests/security -p 'test_*.py'
PYTHONPATH=src python3 tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src python3 -m unittest discover -s tests/unit -p 'test_*.py'
```

Results: engineering 118/118, Shell 47/47, natural integration 2/2,
contract 53/53, architecture 41/41, security 18/18, and all 400 schemas pass.
The full unit run executes 1,455 tests and has exactly eight failures, all from
the unavailable verifier sandbox on this host. Direct probing reports
`kernel.apparmor_restrict_unprivileged_userns=1`; `aa-exec` reports that profile
`fam-os-userns` does not exist; Bubblewrap reports
`loopback: Failed RTM_NEWADDR: Operation not permitted`.

## Evidence and artifacts

- `docs/decisions/0202-natural-engineering-effects-require-core-binding-and-two-owner-checkpoints.md`
- Larry full-unit log: `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T07-02-43-292Z.log`
- No signed installed evidence has been claimed for this change.

## Known limitations and risks

- The currently running service predates this source composition and must not
  be used as installed evidence.
- The old activated `0.1.0` release may not contain the newly required signed
  engineering recipes.
- A failed post-apply verifier safely prevents Git delivery, but an explicit
  owner rollback path after a successful apply is not yet exposed here.
- High-risk authorities remain denied by this ordinary-language route until
  their dedicated owner ceremonies are attached.

## Operational notes

Do not weaken or skip the verifier sandbox. After building the next signed
release, the owner administrator must install its immutable `fam-os-userns`
profile under `/etc/apparmor.d/` and load it with `apparmor_parser` before
installed verification qualification.

## Recommended next entry point

Advance Phase 30.1/30.5/30.9 from `source_composed` to `installed_tested`:
finish publication/rollback and governance attachments, build the signed
release, load the immutable host profile through owner administration, run the
real Console and Shell natural-language lifecycle, and only then update direct
integration coverage. Continue the independent Phase 27/29 gaps afterward.
