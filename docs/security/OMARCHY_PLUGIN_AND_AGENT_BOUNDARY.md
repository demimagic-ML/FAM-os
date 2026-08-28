# Omarchy plugin and agent security boundary

FAM's Omarchy integration has two independent trust domains. The `fam-os`
package runs the agent as the logged-in user. The `fam.os` plugin runs inside
Omarchy's unsandboxed Quickshell process and is intentionally a small,
read-only controller. Package and plugin releases are signed independently by
the pinned FAM release key.

## Runtime identities and privilege

- The main service is a systemd **user** service with `NoNewPrivileges=true`.
- Setup refuses root. Pacman is the only installation step invoked through
  `sudo`; neither setup nor the agent receives blanket passwordless sudo.
- FAM has no generic privileged helper and the widget exposes no shell command.
- System-wide changes require a separately defined capability and confirmation;
  selecting Full OS does not silently turn the service into root.

## Workspace and application authority

Filesystem work remains bounded to the workspace selected by the owner. The
same normalized workspace grant is carried into the isolated candidate,
verification and final apply lifecycle. Symlinks or path traversal cannot be
used to widen that grant.

Screen capture and input control are separate global switches layered over an
exact-window allowlist. They are disabled when the private fallback policy is
absent. Capture requires an approved application ID, process ID and compositor
window ID. Input also requires capture, explicit action enablement, focused
window revalidation and allowed input kinds/keys.

```bash
fam-os permissions desktop
fam-os permissions desktop --screen-capture off
fam-os permissions desktop --input-control off
```

Enabling a switch cannot create or broaden targets. Owner-approved target
configuration remains mode `0600`, and all application actions retain their
normal confirmation and postcondition receipts.

## Widget transport

The service listens on loopback only. A per-start token is stored mode `0600`
under `$XDG_RUNTIME_DIR/fam-os`; restart invalidates old tokens. Widget GET,
WebSocket and POST traffic is authenticated, POST bodies are bounded, WebSocket
origins are restricted, and repeated POSTs use command IDs for idempotency.

The widget may pause, resume or cancel a goal, send guidance, open the Console,
or open the active candidate. It cannot choose a path, execute a command,
change authority or read arbitrary files. Accepted controls are appended to a
mode `0600` audit log under `$XDG_STATE_HOME/fam-os/widget/` without recording
guidance text.

## Failure containment

Plugin state is never written into the Git checkout. QML subprocesses are
asynchronous, polling fallback is no faster than 30 seconds, WebSocket
reconnect uses bounded exponential backoff, events are limited to 64 KiB and
malformed data is ignored. If FAM is unavailable or protocol versions are
incompatible, the widget hides quietly while the agent and active goal remain
independent of the shell process.

The plugin checkout origin and signed `HEAD` are verified at install and every
update. Normal removal preserves FAM goals and history; only
`fam-os purge --user-data --yes` erases the explicit FAM XDG roots.
