# ADR 0118: Production installation consumes signed offline release bundles

**Status:** Accepted  
**Date:** 2026-07-17

## Context

The earlier installer could copy a source checkout into a prefix. That path did
not prove that the installed product matched a reviewed release, included every
runtime component, or could be reproduced without the development tree.

## Decision

Production install and update commands accept only a complete release bundle
whose portable manifest verifies with a configured Ed25519 trust key. A bundle
contains an offline Python wheelhouse, public schemas, expert packages, the
compiled VS Code connector, Console assets, service units, and ordered database
migrations.

Installation extracts only validated relative archive members, installs Python
dependencies without network access into a staged release, performs import and
asset health checks, then atomically switches the active release. Update,
rollback, repair, diagnosis, and removal use the same release manager. Source
checkout copying is not a production installation path.

## Consequences

- A release can be installed and repaired without the repository or network.
- The signing key ceremony and trusted public-key distribution become release
  operations that must be completed before a production candidate ships.
- Adding a production component requires adding it to release assembly and the
  signed manifest, not relying on files that happen to exist in a checkout.
- Development helpers may retain source-oriented behavior, but the product CLI
  must not expose it as install or update behavior.

