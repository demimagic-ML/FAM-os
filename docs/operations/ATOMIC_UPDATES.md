# Atomic updates and rollback

Every production update is a signed `fam.product.update/v1alpha1` release with at
least one service, schema, expert, and connector component. Each component is
SHA-256 verified before staging. Staged files are read-only, and activation is a
single filesystem pointer replacement after the complete release passes health
checks. The prior release remains installed for explicit rollback.

Never edit an activated release in place. A repair creates a new release. If
power is lost before pointer replacement, the old release remains active; stale
`.staging` trees are non-authoritative and may be deleted during diagnosis.
