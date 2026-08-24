# Handoff 0236: Signed installed natural local delivery

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, and 30.9  
**Status:** Partial (`installed_tested` ordinary local slice)  
**Previous handoff:** `0235-natural-language-verified-local-delivery.md`

## Objective

Qualify the ordinary local natural-language engineering lifecycle from a fresh
signed installation through both Console and Shell, and remove discrepancies
between model-proposed operations, exact approved effects, and Git delivery.

## Scope completed

- Core excludes digest-identical replacements before candidate edits and the
  changeset checkpoint; an all-no-op plan is rejected truthfully.
- Candidate generation now semantically validates a parsed plan against the
  trusted candidate state before recording it as validated. State-conflicting
  create/replace/move/delete proposals receive one bounded corrective model
  turn rather than producing a product-level conflict.
- A fresh seven-component Ed25519-signed release was installed healthily with
  the packaged module imported from the immutable installation prefix.
- The authenticated Console completed a plain-language request through grant,
  bounded generation, candidate verification, exact one-file approval, apply,
  owner-tree reverification, and a clean evidence-bound local commit.
- Restarting the same installed service reconstructed the committed outcome and
  did not produce a second commit.
- The installed same-owner Unix Shell completed the same lifecycle from a
  selected folder and displayed separate grant and exact-diff approvals plus a
  verified terminal action receipt.

## Explicitly not completed

- Optional remote publication and its separate approval.
- An explicit owner rollback control after a successful apply.
- Installed attachment of documentation, incident, and independent-review
  governance to the natural orchestrator.
- Phase 27.11--27.16, Phase 29.7--29.8, both-profile qualification, the final
  24-hour soak, or independent human security review.
- Loading the root-owned `fam-os-userns` AppArmor policy on this host.

## Architecture and decisions

ADR 0202 remains controlling. Semantic plan repair is validation before effect,
not an authority expansion: the model receives no trusted hashes, recipes,
approval, or execution session. Exact approved effects still come only from
Core binding against the candidate baseline.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/candidate_generation_binding.py` | Filter digest-identical replacements and reject empty effective plans |
| `src/fam_os/core/engineering/candidate_generation_service.py` | Bounded semantic validation and corrective generation turn |
| `tests/unit/test_candidate_generation.py` | No-op filtering regressions |
| `tests/unit/test_candidate_generation_service.py` | State-conflict repair regression |
| `artifacts/product/phase30/natural-local-delivery-20260719-01/evidence.json` | Machine-readable installed Console/Shell evidence |
| `MASTER_PLANv2.md` | Installed ordinary-slice evidence and remaining scope |
| `MASTER_PLANv2_COMPLETION_PROMPT.md` | Current continuation baseline |

## Public interfaces

No new public authority was added. Candidate plans that are syntactically valid
but incompatible with trusted candidate state now consume a bounded repair
attempt before they can be persisted as `plan_validated`.

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_candidate_generation \
  tests.unit.test_candidate_generation_service \
  tests.unit.test_natural_engineering_execution \
  tests.unit.test_local_git_delivery_service
.verification-venv/bin/python -m unittest discover -s tests/unit -p 'test_*engineering*.py'
.verification-venv/bin/python -m unittest discover -s tests/unit -p 'test_fam_shell*.py'
.verification-venv/bin/python -m unittest \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_console_natural_engineering -v
.verification-venv/bin/python -m unittest discover -s tests/contract -p 'test_*.py'
.verification-venv/bin/python -m unittest discover -s tests/architecture -p 'test_*.py'
.verification-venv/bin/python -m unittest discover -s tests/security -p 'test_*.py'
.verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
.verification-venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'
```

Results: focused candidate/delivery tests 9/9, engineering 119/119, Shell
47/47, natural integration 2/2, contract 53/53, architecture 41/41, security
18/18, and 400/400 schema artifacts pass. The complete unit run executes 1,459
tests and retains exactly eight verifier-dependent failures. The host has
`kernel.apparmor_restrict_unprivileged_userns=1` and no loaded
`fam-os-userns` profile, so the production Bubblewrap verifier fails closed.

Installed Console evidence records one bounded semantic repair, removal of an
unchanged proposed `test_app.py` replacement from the approved effects, two
passing signed verification records, exactly one clean commit, and committed
state recovery after restart. Installed Shell evidence records both approvals,
two passing verification records, and exactly one clean commit.

## Evidence and artifacts

- `artifacts/product/phase30/natural-local-delivery-20260719-01/evidence.json`
- Signed release ID: `phase30-natural-installed-20260719-3`
- Release manifest SHA-256:
  `dad8686a22fc4681d16f40b3f7944ced9986d42916c2823f7f0e292de2521c9f`
- Wheel SHA-256:
  `86bba92382d3a0e764ab1bde9762c4320aea400d550ea3eaa5c2cd56bcc1c16c`
- Full-unit log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T07-29-38-691Z.log`

## Known limitations and risks

- This proves the ordinary single-repository local-code slice only. It is not
  evidence for every Phase 30 lifecycle noun or the Phase 30 exit gate.
- The signed installer wrapper currently records the builder interpreter path;
  packaged imports are prefix-bound, but final clean-room qualification must
  use a builder/interpreter location outside the source checkout.
- Post-apply verifier failure blocks Git delivery, but explicit owner-driven
  rollback after a successful apply remains to be exposed through this route.
- Host sandbox qualification remains external-owner work; required enforcement
  must not be skipped or weakened.

## Recommended next entry point

Continue Phase 30.1 as the integration spine: attach explicit rollback and
separately approved publication, then documentation/incident/review governance
and the remaining auxiliary services. After the path is frozen, rebuild from a
clean external builder, load the owner-administered AppArmor profile, rerun both
hardware profiles, and only then advance final qualification coverage.
