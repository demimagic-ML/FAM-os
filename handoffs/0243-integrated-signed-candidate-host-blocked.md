# Handoff 0243: Integrated signed candidate, host blocked

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.7, 30.9, and 31.2  
**Status:** Partial (`installed_component_tested`; live qualification blocked)  
**Previous handoff:** `0242-restart-safe-automatic-feature-branching.md`

## Objective

Build and install the source-composed rollback, separate publication, incident
controls, and automatic feature branching as one signed candidate, then
truthfully identify the next installed-product gate without changing the live
owner service.

## Scope completed

- Built wheel SHA-256
  `ec0673085c288be17645a0f08cf7c93030e7287a41dce918166df9915bd48100`
  from the current integrated source.
- Built a seven-component Ed25519-signed release
  `phase30-integrated-20260719-1`.
- Installed it healthily at the isolated prefix
  `/tmp/fam-os-phase30-integrated-install-20260719-1`.
- Verified that `fam_os` imports from the immutable installed prefix, not the
  checkout, using the durable `/usr/bin/python3.12` launcher identity.
- Verified that the installed contracts contain automatic branch action/receipt
  fields, incident list/advance operations, the incident advance request, and
  all 406 schema descriptors.
- Ran 62 affected unit, contract, integration, Console, Shell, natural rollback,
  natural publication, incident, and Git tests with the installed package first
  on `sys.path`; all passed with zero failures and zero errors.
- Ran the installed host-security diagnostic and preserved its fail-closed
  `unavailable` receipt.

## Explicitly not completed

- A live installed natural lifecycle using the production Bubblewrap verifier.
- Promotion or restart of the owner service on `127.0.0.1:8765`.
- Both hardware/dependency profile qualification, the 24-hour soak, and human
  security review.
- Full incident response, remaining governance, Phase 27 auxiliary powers, and
  Phase 29.7/29.8 delivery.

## Architecture and decisions

No new durable decision was made. The candidate preserves ADRs 0205–0208. The
host failure is treated as an environmental prerequisite, not as permission to
remove namespace isolation or weaken verifier policy.

## Files changed

| Path | Purpose |
|---|---|
| `artifacts/product/phase30/integrated-source-path-install-20260719-01/evidence.json` | Machine-readable signed installation, installed-package tests, and host blocker. |
| `MASTER_PLAN.md` | Correct companion status. |
| `MASTER_PLANv2.md` | Record current source/installation maturity without closing Phase 30. |
| `MASTER_PLANv2_STATUS_AUDIT.md` | Point the installed gate at the exact candidate and host prerequisite. |
| `MASTER_PLANv2_COMPLETION_PROMPT.md` | Continue from the integrated signed candidate. |

## Public interfaces

No additional interface beyond Handoffs 0241–0242. This handoff packages and
tests those interfaces from one signed artifact.

## Validation

```bash
.verification-venv/bin/python -m pip wheel . --no-deps \
  --wheel-dir /tmp/fam-os-phase30-integrated-20260719-1/wheelhouse
env PYTHONPATH=src:. .verification-venv/bin/python tools/build_signed_release.py \
  --release-id phase30-integrated-20260719-1 \
  --wheelhouse /tmp/fam-os-phase30-integrated-20260719-1/wheelhouse \
  --key-id phase30-natural-test-5 \
  --private-key /tmp/fam-os-phase30-final-signed-4/private.pem \
  --output /tmp/fam-os-phase30-integrated-20260719-1/bundle \
  --repository .
```

Result: one wheel built; seven signed components assembled.

```bash
env PYTHONPATH=src:. .verification-venv/bin/python -m fam_os.product.cli \
  --prefix /tmp/fam-os-phase30-integrated-install-20260719-1 \
  --trusted-key phase30-natural-test-5=/tmp/fam-os-phase30-final-signed-4/public.pem \
  install --bundle /tmp/fam-os-phase30-integrated-20260719-1/bundle
/tmp/fam-os-phase30-integrated-install-20260719-1/bin/fam-os \
  --prefix /tmp/fam-os-phase30-integrated-install-20260719-1 diagnose
```

Result: signed installation healthy, zero issues, no checkout import.

```bash
/usr/bin/python3.12 -I <installed-package-first 62-test runner>
```

Result: 62 tests passed in 3.503 seconds; installed module was
`/tmp/fam-os-phase30-integrated-install-20260719-1/active/python/fam_os/__init__.py`.

```bash
/tmp/fam-os-phase30-integrated-install-20260719-1/bin/fam-os \
  --prefix /tmp/fam-os-phase30-integrated-install-20260719-1 \
  host-security diagnose
```

Result: exit 1; `fam-os-userns` could not be applied, status `unavailable`,
isolation `none`. This is the required fail-closed behavior.

## Evidence and artifacts

- `artifacts/product/phase30/integrated-source-path-install-20260719-01/evidence.json`
- `/tmp/fam-os-phase30-integrated-20260719-1/bundle/manifest.json`
- `/tmp/fam-os-phase30-integrated-install-20260719-1/.fam-os-signed-installation.json`

## Known limitations and risks

- `/tmp` evidence is suitable for the current qualification session but is not
  a durable release archive; the repository evidence JSON preserves identities
  and hashes.
- Installed-package test success uses deterministic fixture verifiers. It is
  not equivalent to a live installed production-verifier lifecycle.
- The root-owned AppArmor profile must be loaded outside this unprivileged task
  before live verifier qualification can pass.

## Operational notes

The isolated prefix and bundle remain under `/tmp`. No active release symlink,
user systemd unit, live port, owner project, or remote provider was changed.

## Recommended next entry point

While the host prerequisite remains external, continue source composition of
Phase 30.6 documentation and 30.8 independent review into the same natural task.
When the owner loads `fam-os-userns`, rerun the live Console/Shell natural
rollback/publication scenarios from this or a newer frozen signed candidate.
