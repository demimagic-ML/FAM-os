# ADR 0163: Console launchers follow installation runtime identity

Status: Accepted

## Context

The installed service was running with runtime root
`/run/user/1000/fam-os-current`, while the lifecycle CLI defaulted every
Console launch to `/run/user/1000/fam-os`. Both directories contained valid,
owner-private tokens, but only the first belonged to the service on port 8765.
The browser therefore rejected the stale token. Separately, `xdg-open` remained
attached to the desktop browser for longer than the synchronous ten-second
timeout; the browser opened, but the CLI killed the launcher and reported
failure.

## Decision

When the Console command has no explicit `--runtime-root`, the lifecycle CLI
derives the runtime directory name from the absolute installation prefix. An
installation ending in `fam-os-current` therefore uses
`$XDG_RUNTIME_DIR/fam-os-current`. Explicit runtime-root selection remains
available for nonstandard service layouts.

The Linux browser adapter starts `xdg-open` in a new session with closed file
descriptors and null standard streams. Immediate nonzero exit and spawn failure
remain failures. A process still attached after a short handoff window is
accepted as successfully handed to the desktop instead of being terminated.

## Consequences

- The normal installed command uses the token owned by the corresponding
  installation/service identity.
- A stale generic runtime token cannot silently authenticate to another live
  service.
- Long-lived desktop launcher behavior no longer turns a successfully opened
  browser tab into a CLI traceback.
- Custom service runtime roots still require the explicit option.

## Alternatives considered

- Search every runtime directory for a token: rejected because a loopback port
  does not prove which private token belongs to it.
- Keep the generic default and document a mandatory option: rejected because
  the installed launcher should work from its installation identity.
- Wait longer for `xdg-open`: rejected because desktop launchers are allowed to
  remain attached and a longer timeout only delays the same false failure.

## Evidence

- `src/fam_os/product/cli.py`
- `src/fam_os/adapters/linux/console_browser.py`
- `tests/unit/test_product_cli.py`
- `tests/unit/test_console_browser.py`
- `artifacts/product/phase19/console-launch-20260718.json`
- `handoffs/0186-authenticated-console-launch-correction.md`
