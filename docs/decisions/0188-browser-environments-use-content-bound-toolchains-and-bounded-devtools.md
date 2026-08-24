# ADR 0188: Browser environments use content-bound toolchains and bounded DevTools

Status: Accepted

## Context

Phase 27.13 requires a real browser environment, but a browser binary is a
large host toolchain and Chrome DevTools is a powerful remote-control protocol.
Passing arbitrary browser argv, trusting an unversioned host installation, or
exposing a raw DevTools session would bypass signed recipe, workspace, output,
and network boundaries.

The host Firefox launcher was a Snap stub and failed inside the namespace. The
first Chrome trial also failed because Chrome requires its debugging port in a
single `--remote-debugging-port=<port>` argument. Both failures cleaned their
exact scopes and left no process authority behind.

## Decision

The process backend admits browser services as another signed fixed-recipe
kind. A browser recipe may name root-owned host toolchain directories only
through `ToolchainMount` declarations containing their exact tree SHA-256 and
an absolute sandbox destination. Admission recomputes the tree digest before
effect and Bubblewrap mounts the matching directory read-only. The candidate
workspace remains the only writable project input.

Recipe port replacement permits exactly one declared `{port:name}` token in a
fixed signed argument, including a fixed prefix or suffix. Any other brace,
unknown port, or repeated placeholder fails before process launch.

Browser control uses a bounded client rather than returning a raw connector.
It reads targets only from the declared `127.0.0.1` port, accepts only the exact
loopback WebSocket endpoint, masks client frames, rejects masked or oversized
server frames, bounds expressions and responses, and exposes only explicit
operations. The initial operations are return-by-value expression evaluation
and bounded strict-base64 PNG capture.

The generic complete release does not automatically bind whichever Chrome is
installed on its build or target host. Product browser enablement requires a
separately installed, release-signed recipe/toolchain package whose declared
digest matches the target. The current physical test signs an exact recipe for
this host's root-owned Chrome tree and proves the installed adapter code, but
does not claim a portable production browser package.

## Consequences

- Browser launch remains behind Core grant and permit admission and the same
  durable cleanup/reconciliation lifecycle as process and API services.
- Replacing the browser tree after recipe signing fails before launch.
- DevTools is loopback-only and capability-shaped; models and clients do not
  receive its WebSocket session.
- Large browser tree hashing adds launch cost and should eventually be backed
  by installed-package verification metadata without weakening digest checks.
- Browser egress remains denied by the process scope; allowlisted external
  browser access is separate policy work.

## Alternatives considered

- Trust `/usr/bin/firefox` or `/usr/bin/google-chrome` by path alone: rejected
  because the referenced implementation can change outside release trust.
- Expose Selenium or raw CDP sessions: rejected because either would create a
  second uncontrolled action authority.
- Embed the host Chrome digest in every generic release: rejected because the
  release would silently become specific to one host package version.

## Evidence

- `src/fam_os/adapters/integration/process_environment.py`
- `src/fam_os/adapters/integration/process_toolchains.py`
- `src/fam_os/adapters/integration/devtools_client.py`
- `tests/unit/test_bounded_devtools_client.py`
- `tests/integration/test_real_browser_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt5.json`
