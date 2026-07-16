# FAM Shell MVP

## Purpose

Phase 5.8 provides the first user-facing FAM_OS interface. `fam-shell` is a
plain terminal application for selecting context, asking Core to perform work,
seeing the execution plan and progress, approving or denying prepared actions,
cancelling work, and receiving only Core-released terminal results.

The Shell is an unprivileged client. It does not load models, route tasks,
create permissions, execute application capabilities, decide verification, or
release candidate content. Those authorities remain in Core.

## User commands

```text
context add KIND RESOURCE [DISPLAY_NAME] [CAPABILITY ...]
context remove CONTEXT_ID
contexts
ask [--verify] PROMPT
refresh
status
approve
deny
cancel
help
quit
```

Context kinds are `application`, `file`, `selection`, and `uri`. A selected
context contains a stable resource reference and optional capability IDs, not
the resource's ambient content. Core remains responsible for resolving the
reference under current permissions. Context is frozen while a request is
active so the displayed selection cannot silently diverge from the submitted
request.

`status` displays the last accepted snapshot. `refresh` requests a newer Core
snapshot. This initial interface uses explicit refresh rather than background
threads; the protocol supports monotonic snapshot revisions without making the
terminal own task scheduling.

## Presentation contract

`fam.shell/v1alpha1` defines versioned documents for:

- selected context and Ask commands;
- snapshot queries;
- revision-bound approval/denial and cancellation commands; and
- session snapshots containing plan steps, progress, optional approval, and an
  optional terminal result.

Snapshots have an immutable session/request identity and monotonically
increasing revision. Equal revisions must be byte-equivalent at the domain
level, and a terminal snapshot is absorbing. A plan's step identity and order
cannot change after first presentation. At most one step is active.

An approval exists only in `waiting_approval` state. Decisions carry the exact
approval ID and expected revision. A result exists only in terminal state.
Failed or withheld results cannot contain candidate content; verified results
must identify evidence. `project_shell_snapshot` converts trusted Core lifecycle
and `TaskResult` values on the server side, so the client does not interpret
internal failure or model state.

## Local transport

The installed client connects to a configurable absolute Unix-domain socket;
the default is `$XDG_RUNTIME_DIR/fam-os/shell.sock` or the equivalent current
user runtime directory. The client refuses non-sockets, symlinks, endpoints not
owned by its effective UID, and modes other than `0600`.

The server requires a private owned parent directory, creates a `0600` socket,
and authenticates every connection with Linux `SO_PEERCRED` before reading one
request. Each request uses a fresh connection in the MVP. Frames are canonical
UTF-8 JSON with a four-byte length prefix and a default 1 MiB limit. Envelopes
have exact fields, version, message kind, typed schema document, message ID, and
response correlation ID. Unknown, malformed, oversized, wrong-schema, and
wrong-correlation data fail closed.

The Core-side `ShellCoreGateway` implements the same Ask/snapshot/decision/cancel
surface behind `ShellRequestDispatcher`. Gateway exceptions become stable
content-free errors; provider exception text never reaches the terminal.

This is authenticated same-user session IPC, not package attestation or a
hardened boundary against another process already running as that user.

## Terminal safety and accessibility

Rendering is color-free and does not depend on cursor motion, Unicode icons, or
mouse input. Stable ASCII markers show pending, active, successful, denied,
failed, cancelled, unavailable, and expired steps. All terminal control bytes,
including escape sequences, are neutralized before rendering. Multiline result
content may keep newlines, but cannot emit terminal control sequences.

The terminal catches client/provider exceptions and prints a fixed safe failure
message. It renders context display names rather than resource references, which
avoids exposing private paths in normal context listings.

## Running

After installing the package:

```bash
fam-shell
fam-shell --socket /absolute/private/path/shell.sock --timeout 10
```

The Core service owns the corresponding `UnixShellServer` and gateway. The
Phase 5.8 integration test retains a deterministic fake gateway for isolated UI
testing. Phase 5.12 adds the real vertical composition through the same socket,
controller, and terminal: scoped file observation, a bounded test, native VS
Code observation/edit, official-SDK MCP context, explicit approval, trusted
postconditions, durable audit, and MCP-unavailable degradation. See
`../operations/CROSS_APPLICATION_ACCEPTANCE.md` and ADR 0050.
