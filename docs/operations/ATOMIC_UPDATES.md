# Atomic updates and rollback

Every production update is a signed `fam.product.update/v1alpha1` release with at
least one service, schema, expert, and connector component. Each component is
SHA-256 verified before staging. Staged files are read-only, and activation is a
single filesystem pointer replacement after the complete release passes health
checks. The prior release remains installed for explicit rollback.

Never edit an activated release in place. If power is lost before pointer
replacement, the old release remains active; stale `.staging` trees are
non-authoritative and may be deleted during diagnosis.

The owner-private installation marker
`fam.product.signed-installation-marker/v1alpha2` records every generated
launcher, generated systemd unit, and retained public trust key by safe relative
path and SHA-256 digest. Diagnosis reads this expected ledger instead of
globbing the files that happen to remain, so deletion and content modification
both make the installation unhealthy.

Repair never modifies the activated signed release. It verifies that active
release, regenerates only the stable launchers, units, and trust material that
are derived from it, and atomically writes a new expected-file ledger. A legacy
path-only marker is readable but remains unhealthy until repair or update
upgrades it. Damage inside the signed active release requires a signed update or
rollback; it is not repaired in place.
