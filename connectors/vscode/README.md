# FAM_OS VS Code Semantic Connector

This extension makes a running Visual Studio Code instance a permissioned native
Application Fabric capability provider. It does not contain a model, contact a
remote service, run shell commands, or bypass FAM Core permission, confirmation,
postcondition, and audit policy.

## Capabilities

| ID | Authority | Surface |
|---|---|---|
| `vscode.editor.active` | Observe | Active URI, language, selection, version, dirty state, and visible ranges; no text. |
| `vscode.editor.selection` | Observe | Explicitly authorized selected text, bounded by the lower of request and configured limits. |
| `vscode.diagnostics.active` | Observe | At most 200 bounded active-document diagnostics. |
| `vscode.workspace_edit.apply` | Modify | At most 64 exact range replacements against a full version-and-SHA-256 revision. |
| `vscode.workspace_edit.undo` | Modify | One bounded in-memory reversal token, valid only while the edited buffer still matches. |

The connector deliberately does not expose save, terminal, task, source-control,
extension-installation, generic command, network, or arbitrary filesystem
capabilities.

## Development

```bash
npm install
npm test
```

`npm test` compiles against the pinned VS Code 1.110 API types, runs pure Node
tests for framing, schemas, revisions, edit planning, and reversal bounds, then
runs a cross-language test against FAM_OS's Python authenticated Application
Fabric codec.

To run an Extension Development Host, open this directory in VS Code and use an
extension-development launch configuration or invoke Code with this directory as
its extension development path. The Core Application Fabric server must already
own a private `0600` Unix socket.

## Connection

The connector is off by default. Run `FAM_OS: Connect Semantic Connector` from
the command palette, or enable `famOS.connector.autoConnect`. The default socket
is `$XDG_RUNTIME_DIR/fam-os/applications.sock`; an absolute override can be set in
`famOS.connector.socketPath`.

Before connecting, the extension verifies that the endpoint is a Unix socket,
owned by the current UID, with mode `0600`. It registers over
`fam.applications.local/v1alpha1`, uses bounded canonical frames, accepts only
typed observation/preparation/confirmation requests, and correlates every
response. Disconnect invalidates pending operations, prepared proposals, and
reversal tokens.

## Edit and reversal semantics

A document revision is:

```text
vscode-document:<TextDocument.version>:<sha256 of current UTF-8 text>
```

Preparation rejects a stale revision, a document outside the workspace, a
document above 1,048,576 JavaScript characters, more than 64 edits, more than
262,144 replacement characters, invalid UTF-16 positions, duplicate-position
inserts, and overlapping ranges. It computes the exact expected post-edit hash
without mutation and returns a preview.

After Core confirmation, execution rechecks the complete revision, applies a
VS Code `WorkspaceEdit`, and reports hash/version postcondition evidence. It
returns verified status only when both pass. The in-memory reversal record holds
the bounded pre-edit text and the exact required post-edit revision. Undo refuses
to run after any intervening buffer change and produces a new inverse token on
success. Tokens are never persisted and the oldest is evicted above 64 records.

The connector verifies editor-buffer state, not saved disk state or workspace
tests. Core must compose deterministic file hashes/tests when the task requires
those stronger postconditions.

## Packaging status

This Phase 5.9 source package and lockfile are reproducible and compile against
the installed reference VS Code. Signing, registry installation, package trust,
automatic update, and production sandbox lifecycle belong to Phase 6 and later
deployment work.
