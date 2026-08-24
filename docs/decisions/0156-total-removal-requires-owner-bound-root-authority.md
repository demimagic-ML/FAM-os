# ADR 0156: Total removal requires owner-bound root authority

Status: Accepted

## Context

Phase 23.8 requires total removal from a fresh user profile. The existing
`fam-os remove` command stopped `fam-os.service`, removed its unit link, and
deleted only the signed prefix. It left encrypted databases, identities, model
storage, runtime tokens and sockets, a possible transient `fam-ollama.service`,
and the managed VS Code extension.

Accepting arbitrary `--state-root` or `--runtime-root` paths for recursive
deletion would be worse than leaving those files behind.

## Decision

State and runtime roots receive a private owner-bound marker when the product
initializes them. The marker binds contract version, exact resolved path,
purpose, and effective UID. Complete removal requires literal `--confirm` and
validates all authorities before stopping a service or deleting bytes.

The removal order is:

1. validate the signed-installation marker, non-overlapping roots, owner/mode,
   exact state/runtime markers, and connector management identity;
2. disable and stop `fam-os.service` and `fam-ollama.service`;
3. remove only the installation-owned user-unit link and reset failed units;
4. remove only connector directories with an exact FAM marker identity;
5. remove marked runtime and durable state/model roots;
6. remove the signed installation prefix last.

`SignedBundleInstallation.remove()` remains the narrow prefix-only primitive
for isolated candidate harnesses. `CompleteProductRemoval` owns the user-facing
product lifecycle.

## Consequences

- The normal removal command now removes every user-owned FAM surface and emits
  a structured receipt.
- Unmarked, symlinked, wrongly owned, mode-unsafe, moved, repurposed, or
  overlapping roots fail before any service mutation.
- Existing pre-marker roots are not guessed to be safe. Starting the corrected
  service writes the marker; otherwise manual migration is required.
- The system-wide AppArmor profile is deliberately separate. Removing one
  user's installation cannot know whether another user still depends on it.
- The new Phase 23.8 runner exercises install, update, rollback, repair,
  connector installation, service startup, verifier isolation, and total
  removal through installed commands.

## Alternatives considered

- Delete the default paths without markers: rejected because CLI overrides and
  symlink/path mistakes could destroy unrelated data.
- Treat prefix-only removal as total removal: rejected because durable identity,
  memory, models, credentials, and integration code would remain.
- Delete every VS Code directory matching a name prefix: rejected because a
  filename is not management authority.
- Remove the AppArmor profile automatically: rejected because it is a shared
  host policy requiring separate administrator intent.

## Evidence

- `src/fam_os/product/owned_root.py`
- `src/fam_os/product/removal.py`
- `src/fam_os/product/cli.py`
- `src/fam_os/product/service.py`
- `src/fam_os/product/vscode_installation.py`
- `tools/phase23_lifecycle/`
- `tests/unit/test_owned_root.py`
- `tests/unit/test_product_removal.py`
- `tests/unit/test_phase23_lifecycle.py`

