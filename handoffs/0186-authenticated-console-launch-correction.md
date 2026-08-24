# Handoff 0186: Authenticated Console launch correction

**Date:** 2026-07-18  
**Plan step:** Phase 19.14 corrective integration  
**Status:** Source and signed installed correction complete  
**Previous handoff:** `0185-bounded-workspace-tool-loop.md`

## Objective

Make the documented installed Console command open an authenticated browser tab
without a rejected token or a false desktop-launcher timeout.

## Scope completed

- Traced the active transient service and both owner-private runtime tokens.
- Proved the CLI read `/run/user/1000/fam-os/console.token` while the active
  service used `/run/user/1000/fam-os-current/console.token`.
- Made the default Console runtime root follow the installation prefix name.
- Preserved explicit `--runtime-root` override behavior.
- Replaced the synchronous ten-second `xdg-open` wait with a detached handoff
  that still rejects spawn and immediate nonzero-exit failures.
- Added CLI and Linux browser adapter regressions.
- Built, signed, installed, restarted, diagnosed, and live-probed release
  `fam-os-console-launch-20260718-21`.

## Explicitly not completed

- No token value, token digest, cookie, or CSRF value is recorded in evidence.
- The launcher does not search unrelated runtime directories.
- Nonstandard service layouts must continue to pass `--runtime-root` explicitly.
- Phase 21.7 and remaining Phase 23 external gates are unchanged.

## Architecture and decisions

ADR 0163 binds the normal launcher default to installation identity. The
Console fragment remains the private bootstrap transport, but the CLI now reads
it from the service's corresponding runtime directory. Desktop process lifetime
is not treated as HTTP authentication evidence; a separate live session
exchange proves the token-service pairing.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/cli.py` | Prefix-derived Console runtime default |
| `src/fam_os/adapters/linux/console_browser.py` | Detached `xdg-open` handoff |
| `tests/unit/test_product_cli.py` | Runtime derivation regression |
| `tests/unit/test_console_browser.py` | Detached, immediate-failure, and missing-launcher tests |
| `docs/decisions/0163-console-launchers-follow-installation-runtime-identity.md` | Architectural decision |
| `artifacts/product/phase19/console-launch-20260718.json` | Sanitized live evidence |

## Public interfaces

The documented command is unchanged:

```bash
~/.local/share/fam-os-current/bin/fam-os \
  --prefix ~/.local/share/fam-os-current \
  console
```

`--runtime-root` remains an optional override.

## Validation

```bash
.verification-venv/bin/python -m unittest \
  tests.unit.test_console_browser \
  tests.unit.test_console_launch \
  tests.unit.test_product_cli
.verification-venv/bin/ruff check <four changed source/test files>
.verification-venv/bin/mypy \
  src/fam_os/product/cli.py \
  src/fam_os/adapters/linux/console_browser.py
larry run ".verification-venv/bin/python -m unittest discover -s tests -t ."
```

Fourteen focused tests passed; Ruff and Mypy passed. The final complete suite
passed 1,396 tests with two declared skips. Its log is
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T18-55-52-766Z.log`.

The first complete-suite attempt had one transient existing Shell socket error
in the reversal integration test. That exact test passed immediately when
isolated, and the complete suite then passed. No failing result is omitted from
the evidence history.

## Installed proof

The exact unchanged command completed in 0.972 seconds and returned
`authenticated_fragment_used: true` and `opened: true`. The installed release
diagnosed healthy, `fam-os-current.service` remained active, the Console root
returned HTTP 200, and an independent session exchange using the active
service's private token returned HTTP 200 with the expected session fields.

## Evidence and artifacts

- `artifacts/product/phase19/console-launch-20260718.json`
- `docs/decisions/0163-console-launchers-follow-installation-runtime-identity.md`
- Full-suite log:
  `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T18-55-52-766Z.log`

## Known limitations and risks

- Prefix-derived runtime identity assumes the service uses the same installation
  name, which is true for the packaged default and this transient test service.
- A custom runtime layout must use the explicit option.
- Browser startup is asynchronous; successful spawn is followed by Console's
  own token exchange and session checks, which remain the authentication gate.

## Operational notes

The active signed prefix is `~/.local/share/fam-os-current`, release
`fam-os-console-launch-20260718-21`. `fam-os-current.service` is active and the
Console is at `http://127.0.0.1:8765/`.

## Recommended next entry point

Resume the next unblocked Master Plan boundary after the owner confirms the
installed launcher and workspace loop in the browser.
