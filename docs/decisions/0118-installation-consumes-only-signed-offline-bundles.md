# ADR 0118: Installation consumes only signed offline bundles

Status: Accepted

## Context

The former production CLI copied a source directory and was disconnected from
the signed atomic release manager. It omitted dependency wheels, migrations,
compiled connectors, and managed-runtime units.

## Decision

The `fam-os` production CLI installs and updates only portable Ed25519-signed
release bundles. Every bundle contains an offline wheelhouse, generated schemas,
expert packages, compiled connector package, Console assets, service units, and
SQL migrations as independently hashed components. Installation performs an
offline target install, imports the staged runtime, checks every shipped area,
then atomically activates it. Update and rollback switch complete releases.

Stable launchers point through the `active` symlink. Repair recreates stable
managed files only from a healthy signed active release; corrupt immutable
release content requires signed update or rollback. Removal deletes the owned
unit link and installation tree.

## Evidence

- `src/fam_os/product/release_assembly.py`
- `src/fam_os/product/bundle_installation.py`
- `artifacts/product/phase17/signed-installed-release.json`
