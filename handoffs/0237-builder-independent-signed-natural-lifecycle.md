# Handoff 0237: Builder-independent signed natural lifecycle

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.9, and 31.2  
**Status:** Partial (`installed_tested` ordinary local slice)  
**Previous handoff:** `0236-signed-installed-natural-local-delivery.md`

## Objective

Remove the signed installation's dependency on a repository-local builder
virtualenv and requalify the Console and Shell natural-language lifecycle from
the corrected release candidate.

## Scope completed

- Stable launchers and service units now resolve the durable base Python
  interpreter rather than embedding the disposable builder `sys.executable`.
- Runtime Python resolution fails closed unless the path is absolute, existing,
  regular, and executable.
- A new seven-component Ed25519-signed release installed healthily. Its stable
  launchers use `/usr/bin/python3.12`, packaged imports resolve under the active
  installation prefix, and no launcher references the checkout virtualenv.
- The corrected exact release completed both authenticated Console and
  same-owner Shell natural-language lifecycles through signed verification,
  exact approval, apply, reverification, and one clean local commit.
- The Console task reconstructed its committed outcome after service restart
  with no second commit.

## Explicitly not completed

- The full multi-profile and dependency-profile matrix required by 31.2.
- Optional publication, explicit post-success rollback, governance attachment,
  remaining Phase 27/29 capabilities, soak, or human review.
- Loading the required root-owned AppArmor user-namespace profile.

## Architecture and decisions

ADR 0203 requires generated long-lived launchers to use a durable resolved base
interpreter while retaining all signed-release packages under `active/python`.
Ambient `PATH` lookup and builder virtualenv capture are both forbidden.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/installed_launcher.py` | Durable installed interpreter resolution and launcher rendering |
| `src/fam_os/product/bundle_installation.py` | Use the stable interpreter for launchers and units |
| `tests/unit/test_signed_bundle_installation.py` | Builder-independence regression |
| `docs/decisions/0203-installed-launchers-must-not-depend-on-the-builder-environment.md` | Durable runtime identity decision |
| `artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json` | Corrected exact-release lifecycle evidence |

## Public interfaces

No CLI shape changed. Installed `fam-os`, `fam-service`, `fam-shell`, and network
authority/broker launchers now survive removal of the installer virtualenv.

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_signed_bundle_installation \
  tests.integration.test_linux_product_lifecycle -v
```

All four lifecycle/launcher tests pass. The signed release
`phase30-natural-installed-20260719-4` imports FAM_OS from its installation
prefix using `/usr/bin/python3.12`. Direct Console and Shell runs each presented
both owner checkpoints, retained only the effective `app.py` patch, passed one
candidate and one post-apply signed verification, and created exactly one clean
commit. The Console state remained committed after service restart.

## Evidence and artifacts

- `artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`
- Release manifest SHA-256:
  `9aba8ea25e7506ff07e8974c3b3602b8e180f67f51896565d67b9c075177213c`
- Wheel SHA-256:
  `4ef09ee4cb03aefd64f9988be987bfb94ac6d809f9a9b696bb0cd5990daccf19`

## Known limitations and risks

- This corrects one clean-room installation dependency but is not the complete
  31.2 both-hardware/dependency-profile qualification.
- `/usr/bin/python3.12` is host runtime identity, not a FAM_OS-shipped Python
  distribution; its availability remains an installation prerequisite.
- The ordinary local slice remains narrower than the complete Phase 30 wording.

## Recommended next entry point

Attach explicit rollback and separately approved publication to the same
natural task, then compose documentation/incident/review governance. Freeze the
source path before running the full clean signed profile matrix.
