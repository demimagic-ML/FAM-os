# ADR 0203: Installed launchers must not depend on the builder environment

Status: Accepted

## Context

The signed bundle installer correctly installed all Python packages under the
immutable active release, but generated launchers and the systemd unit embedded
`sys.executable`. When installation ran from a repository-local verification
virtualenv, the installed product therefore depended on a disposable builder
path even though imports came from the release prefix. Deleting or relocating
the checkout would make an otherwise healthy signed installation unstartable.

## Decision

Stable installed launchers and generated service units use the resolved base
interpreter (`sys._base_executable`) of the installer process. The resolver
requires one absolute, existing, executable file and fails installation/repair
if that invariant is unavailable. The signed release's `active/python` remains
the complete package and dependency root through an explicit `PYTHONPATH`.

The installer may continue using its current interpreter while unpacking and
health-checking a candidate release. No generated long-lived file may retain a
builder virtualenv or source-checkout interpreter path.

## Consequences

- A signed installation remains runnable when its builder virtualenv or source
  checkout is removed.
- Launchers retain deterministic interpreter identity instead of relying on
  ambient `PATH` or `/usr/bin/env` resolution.
- The installed marker continues to bind launcher and unit content digests, so
  update, rollback, diagnose, and repair observe this runtime identity.
- Truly embedded Python distributions must expose a durable executable as their
  base interpreter or installation fails closed.

## Alternatives considered

- Keep `sys.executable`: rejected because it commonly identifies a disposable
  build or test virtualenv.
- Use `/usr/bin/env python3`: rejected because ambient `PATH` can select a
  different or attacker-controlled interpreter.
- Copy an interpreter into the release: rejected because FAM_OS currently ships
  Python packages, not a separately signed Python runtime distribution.

## Evidence

- `src/fam_os/product/installed_launcher.py`
- `src/fam_os/product/bundle_installation.py`
- `tests/unit/test_signed_bundle_installation.py`
- `tests/integration/test_linux_product_lifecycle.py`
- `artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`

## Superseded decisions

None. This narrows the stable-launcher requirement in ADR 0118 and preserves
the managed-file ledger defined by ADR 0157.
