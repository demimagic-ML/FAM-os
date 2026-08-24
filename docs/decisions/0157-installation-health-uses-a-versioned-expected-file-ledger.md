# ADR 0157: Installation health uses a versioned expected-file ledger

Status: Accepted

## Context

The Phase 23.8 fresh-profile runner deleted the installed `fam-shell` launcher
and expected `fam-os diagnose` to report damage. Diagnosis instead returned
healthy because it defined the managed-file set by globbing files that still
existed. The same design could not detect modified launcher or generated unit
content. The existing installation marker already listed paths, but diagnosis,
receipts, repair, update, and rollback did not consume that list.

## Decision

The signed installation marker is upgraded to
`fam.product.signed-installation-marker/v1alpha2`. It binds the active release
identity and every generated launcher, generated service unit, and persisted
trust key by safe relative path and SHA-256 digest.

- Diagnosis reads the expected ledger, never a current filesystem glob.
- Missing, symlinked, digest-mismatched, invalid-marker, and release-mismatched
  states are unhealthy.
- Only the fixed `bin`, `systemd`, and `trust` installation surfaces are valid
  marker entries.
- Install, update, rollback, and repair regenerate stable files and atomically
  commit their expected ledger after content and modes are final.
- The former path-only marker remains readable but diagnoses as
  `installation_marker_upgrade_required` until a successful update or repair
  writes digests.
- The marker is owner authority, not protection against compromise of the same
  Unix account. Signed active-release components remain independently verified.

## Consequences

- Deleting or modifying a stable launcher or unit can no longer disappear from
  the diagnosis input set.
- Repair can deterministically restore generated stable files from a healthy
  signed active release without modifying that release in place.
- Invalid or unsafe markers fail closed before update, rollback, repair, or
  removal authority is accepted.
- Fresh installations and lifecycle candidates receive the new marker without
  a separate migration command.

## Alternatives considered

- Keep globbing and hard-code only `fam-shell`: rejected because any missing
  launcher, unit, or trust key would retain the same false-health path.
- Store paths without digests: rejected because content tampering would still
  diagnose healthy.
- Rebuild expected paths solely from the active release: rejected because
  generated launchers and persisted trust keys are outside the signed release
  tree.
- Sign the owner marker with the ephemeral release key: rejected because the
  installed product normally retains only public trust material and repair must
  remain locally possible.

## Evidence

- `src/fam_os/product/installation_marker.py`
- `src/fam_os/product/bundle_installation.py`
- `tests/unit/test_installation_marker.py`
- `tools/phase23_lifecycle/`
- `artifacts/product/phase23/lifecycle/phase23-lifecycle-preflight-20260718-04/installed-lifecycle.json`

