# VS Code Native Semantic Connector

## Purpose

Phase 5.9 provides the first high-fidelity native application connector and the
reference TypeScript connector SDK. A Visual Studio Code extension registers a
small semantic capability surface with Application Fabric over the Phase 5.2
authenticated local transport. It turns editor state and explicitly prepared
workspace edits into normal provider-neutral observations, proposals, actions,
and evidence.

The extension does not contain or call an LLM. It cannot grant itself
permission, skip confirmation, release task results, or reach Core model,
routing, verification, or supervisor internals.

## Package layout

`connectors/vscode/src/sdk/` is the reusable reference client:

- strict Application Fabric message and typed-document values;
- canonical 1 MiB length-prefixed framing;
- exact schema/kind validation;
- private Unix-socket ownership/mode validation;
- registration handshake and response correlation;
- bounded operation cancellation and prepared-proposal lifetime; and
- content-free stable connector errors.

`connectors/vscode/src/editor/` is the VS Code adapter. Only the extension
composition and editor adapter files import `vscode`; the transport SDK and
edit-planning algorithms do not. No source imports MCP, a model client,
`child_process`, HTTP, or shell execution.

## Capability surface

| Capability | Authority | Bound or effect |
|---|---|---|
| `vscode.editor.active` | Observe | Active URI/language/selection/version/dirty/line count and at most 16 visible ranges; no text. |
| `vscode.editor.selection` | Observe | Selected text only, bounded to configured/request limits up to 131,072 characters. |
| `vscode.diagnostics.active` | Observe | At most 200 diagnostics with bounded messages/source/code. |
| `vscode.workspace_edit.apply` | Modify | One confirmed, version-and-hash-bound edit of at most 64 nonoverlapping ranges. |
| `vscode.workspace_edit.undo` | Modify | One confirmed reversal while the buffer still matches the exact post-edit revision. |

The connector has no generic VS Code command surface and no save, terminal,
task, source-control, extension-installation, network, or arbitrary filesystem
capability. Those require separate future capability IDs and policies.

Eight connector-owned Draft 2020-12 schemas define the capability parameter and
payload shapes. Application Fabric's generic observation/action schema remains
the outer boundary.

## Observations and privacy

Active-editor metadata does not include document text. The selected-text
capability is separate so permission for metadata is not permission for code
content. Selection reads only the bounded requested range, rather than allocating
then truncating an arbitrarily large selection. Diagnostics omit related
information and are count/string bounded.

For documents within the action-size bound, the observation revision is:

```text
vscode-document:<TextDocument.version>:<sha256 of UTF-8 document text>
```

Documents above 1,048,576 editor characters expose a version-only observation
revision and are ineligible for native workspace-edit actions. This prevents the
edit path from allocating an uncontrolled document copy.

## Workspace-edit lifecycle

Preparation requires all of the following:

- a `file:` URI inside a current VS Code workspace;
- the same URI in the action resource scope and typed parameters;
- an exact full version-and-hash revision;
- one to 64 edits;
- no overlapping or duplicate-position ranges;
- valid VS Code UTF-16 line/character positions;
- at most 262,144 replacement characters; and
- a document at most 1,048,576 editor characters.

Connector registrations encode workspace directories with a trailing `/`.
Core interprets only such explicit `file:` directory scopes hierarchically,
requires the same authority and resource grant, parses matching authorities,
and rejects dot segments. File scopes without the trailing slash remain exact.
This allows an approved document inside a workspace without turning an exact
file scope into a string-prefix permission.

The pure planner computes the exact post-edit SHA-256 without mutation. The
proposal previews ranges/new text, declares document version/hash preconditions,
declares hash/version postconditions, is always-confirmed, and identifies
`vscode.workspace_edit.undo` as its reversal capability.

Execution reopens the workspace document, recomputes the complete revision, and
refuses stale work. Only then does it construct and pass a VS Code `WorkspaceEdit`
to `workspace.applyEdit`. The VS Code API documents `WorkspaceEdit` and
`workspace.applyEdit` in the official [VS Code API reference](https://code.visualstudio.com/api/references/vscode-api).

After application, the connector recomputes buffer hash and version. It returns
verified status only when both expected postconditions pass. A failed
postcondition retains a reversal token because mutation may already have
occurred. This proves editor-buffer state, not saved disk state or workspace
tests; Core must compose deterministic file/test verification when required.

## Reversal

The connector stores at most 64 bounded reversal records in extension memory.
A record contains the pre-edit text and hash plus the exact required post-edit
revision. It is never serialized to Core or disk; Core receives only an opaque
random token.

Undo preparation and execution both reject a different resource URI, different
expected revision, missing/evicted token, or any intervening buffer change. Undo
uses an exact full-document `WorkspaceEdit`, verifies the restored hash and new
version, consumes the token, and produces a new inverse token. Disconnect clears
all proposals, operations, and reversal records.

## Connection and activation

The extension targets VS Code API 1.110 and was compiled on the reference
machine running VS Code 1.114. It is disabled by default. The user can connect
through the `FAM_OS: Connect Semantic Connector` command or enable explicit
auto-connect. VS Code documents extension manifests/activation and registered
commands in its official [Extension Anatomy](https://code.visualstudio.com/api/get-started/extension-anatomy) and [Commands](https://code.visualstudio.com/api/extension-guides/command) guides.

The client verifies an owned `0600` Unix socket, sends registration, and does
not report connected until Core returns the correlated ACK. Workspace-folder
changes reconnect so resource scopes are atomically replaced. Transport loss
fails closed and invalidates all transient authority-bearing state.

## Native transport versus MCP

This connector uses the native Application Fabric transport because the edit
workflow needs the exact generic observation/proposal/confirmation/action
documents, Core-issued permission grants, response-family correlation,
revision-bound reversal state, and connector registration lifecycle already
implemented there.

MCP is not embedded in the extension and is not a permission boundary. A future
editor MCP server can expose read-only semantic tools/resources and FAM's Phase
5.3 adapter can map them into the same registry when that reduces integration
cost. Workspace-edit authority still must pass through Core proposal,
confirmation, postcondition, and audit semantics; adding an MCP method that
bypasses those semantics is forbidden.

## Validation

- TypeScript strict compilation with pinned TypeScript 5.9.3, Node 20 types, and
  VS Code 1.110 types.
- Seven pure Node tests for canonical framing, protocol strictness, UTF-16/CRLF
  edit planning, stale/overlap rejection, capability registration, input shapes,
  and bounded single-use reversal state.
- Cross-language TypeScript client to Python Application Fabric test covering
  registration ACK, observation, action preparation, confirmation, verified
  result, schemas, and correlations.
- Eight connector capability schemas validated as Draft 2020-12.
- Architecture tests confining VS Code imports and prohibiting MCP, model,
  subprocess, shell, and network escape surfaces.
- A Phase 5.12 isolated-profile live run through `ConnectorRequestBroker`, Core
  observation/proposal/approval/action services, trusted live editor
  postconditions, and durable action audit.
- VSCE package listing/package generation to `/tmp`; the extension is not
  installed into the user's normal VS Code profile by this phase.
