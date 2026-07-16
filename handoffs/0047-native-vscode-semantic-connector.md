# Handoff 0047: Native VS Code semantic connector

**Date:** 2026-07-16  
**Plan step:** Phase 5.9  
**Status:** Complete  
**Previous handoff:** `0046-fam-shell-mvp.md`

## Objective

Build the first real level-1 application connector as a small Visual Studio Code
extension plus a provider-neutral TypeScript SDK. Expose bounded editor semantics
and reversible workspace edits through the existing authenticated Application
Fabric lifecycle without embedding model policy or weakening Core authority.

## Scope completed

- Off-by-default VS Code extension with explicit connect/disconnect commands,
  private-socket checks, correlated registration ACK, and workspace-scope refresh.
- Reusable TypeScript native connector SDK with strict canonical 1 MiB frames,
  exact typed documents, cancellation, proposal correlation, and safe errors.
- Separate active-editor metadata, selected-text, and diagnostics observation
  capabilities with count, range, and string bounds.
- Always-confirmed apply and undo capabilities restricted to one file URI inside
  a current workspace and a complete version-plus-SHA-256 document revision.
- Pure UTF-16-aware edit planning with stale, overlap, duplicate-position, size,
  scope, and invalid-position rejection before mutation.
- Immediate buffer hash/version postcondition checks after `WorkspaceEdit` and a
  bounded 64-record, opaque, exact-revision, in-memory reversal store.
- Eight strict connector-owned Draft 2020-12 capability schemas.
- Cross-language proof that the compiled TypeScript SDK registers and completes
  observation, prepare, confirmation, and verified result exchanges against the
  Python Application Fabric transport.
- Reproducible VSIX generation without installing into the user's normal VS Code
  profile.

## Explicitly not completed

- Normal-profile installation, signing, publisher/registry trust, or automatic
  update lifecycle.
- Live Extension Host mutation of a real user document; this phase deliberately
  stops at compiled VS Code API compatibility, pure editor logic, packaging, and
  authenticated cross-language transport.
- Saved-file, compiler, test, or task verification; the connector proves only
  the in-memory editor-buffer postcondition.
- Embedded MCP. Future read-only MCP surfaces can be mapped by the existing MCP
  client adapter, but action authority remains on the native Core lifecycle.

## Architecture and decisions

ADR 0047 chooses native `fam.applications.local/v1alpha1` transport because the
existing observation/proposal/confirmation/action/reversal documents preserve
the exact required semantics. VS Code SDK types remain inside the adapter. The
SDK imports no VS Code, MCP, model, subprocess, shell, HTTP, or supervisor code.
The extension exposes no generic command, terminal, save, source-control,
extension-installation, network, or arbitrary-filesystem capability.

## Files changed

| Path | Purpose |
|---|---|
| `connectors/vscode/package.json` | Pinned extension manifest, commands, settings, scripts, and API target. |
| `connectors/vscode/package-lock.json` | Reproducible Node dependency lock. |
| `connectors/vscode/src/sdk/` | Provider-neutral native connector protocol, framing, validation, and client. |
| `connectors/vscode/src/editor/` | Editor observations, revision/edit planning, provider, and reversal state. |
| `connectors/vscode/src/extension.ts` | Thin VS Code lifecycle and command composition. |
| `connectors/vscode/schemas/` | Eight strict capability input/output schemas. |
| `connectors/vscode/src/test/` | Pure SDK, edit-planning, registration, and reversal tests. |
| `connectors/vscode/test/` | Python transport integration, fixture server, and schema validation. |
| `tests/architecture/test_vscode_connector_boundary.py` | Import, capability, manifest, and size boundary guards. |
| `docs/protocols/VSCODE_SEMANTIC_CONNECTOR.md` | Capability, privacy, lifecycle, reversal, and validation guide. |
| `docs/decisions/0047-native-vscode-semantic-connector.md` | Durable native-transport decision. |
| `docs/protocols/APPLICATION_CONTRACTS.md` | Real connector profile and transport interoperability note. |
| `docs/architecture/APPLICATION_WEAVING.md` | Phase 5.9 implementation status. |

## Public interfaces

- VS Code commands `famOS.connect` and `famOS.disconnect`.
- Settings `famOS.connector.autoConnect`, `famOS.connector.socketPath`, and
  `famOS.connector.maxSelectionCharacters`.
- `NativeConnector`, `NativeCapabilityProvider`, strict message/document types,
  framing codec, and validation functions in the reference TypeScript SDK.
- Capabilities `vscode.editor.active`, `vscode.editor.selection`,
  `vscode.diagnostics.active`, `vscode.workspace_edit.apply`, and
  `vscode.workspace_edit.undo`.
- Eight `vscode.*.v1.schema.json` connector capability schemas.

## Validation

```bash
cd connectors/vscode && npm test
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools connectors/vscode/test
npx --yes @vscode/vsce package --no-dependencies --allow-missing-repository --out /tmp/fam-os-vscode-connector-0.1.0.vsix
python3 <AST Python module/function size gate>
node <TypeScript AST module/function size gate>
larry index . && larry health .
```

Result: strict TypeScript compilation passed; all seven Node tests passed; the
TypeScript-to-Python native transport integration passed; all eight connector
schemas validated; and the VSIX packaged 27 production files at 25.8 KB. Both
Python environments passed all 517 tests, with one expected GI/AT-SPI skip in
the MCP venv and two environment-dependent skips in system Python. All 40 Core
schema artifacts matched and compileall succeeded. All 274 Python implementation
modules and 15 production TypeScript modules remained at or below 300 lines per
module and 50 lines per function. Larry indexed 715 files / 2,149 symbols with
10,304 nodes / 37,519 edges and clean health. The persisted code graph was
refreshed to the same 10,304-node / 37,519-edge source view.

VSCE emitted one expected non-blocking warning because this pre-publication,
`UNLICENSED` package intentionally has no LICENSE file yet.

## Evidence and artifacts

- `docs/protocols/VSCODE_SEMANTIC_CONNECTOR.md`
- `docs/decisions/0047-native-vscode-semantic-connector.md`
- `connectors/vscode/test/native_transport_integration.py`
- `tests/architecture/test_vscode_connector_boundary.py`
- `/tmp/fam-os-vscode-connector-0.1.0.vsix` (ephemeral local package)

## Known limitations and risks

- Same-UID Unix peer authentication cannot distinguish an unauthorized process
  running as the same desktop user; package attestation is future work.
- Reversal authority is intentionally lost on disconnect, extension restart, or
  bounded-record eviction.
- JavaScript string bounds are conservative editor-character bounds, while the
  hash is over UTF-8; this is documented rather than represented as a byte cap.
- Buffer verification does not prove disk save, compilation, tests, or overall
  task correctness.
- No real user workspace was modified during validation.

## Operational notes

No connector socket, VS Code Extension Host, model, MCP server, or persistent
service was left running. `node_modules/` and compiled `out/` are ignored local
development artifacts. The package is available only at the ephemeral `/tmp`
path and is not installed. The default endpoint is
`$XDG_RUNTIME_DIR/fam-os/applications.sock` and must already be owned by a
private Application Fabric server.

## Recommended next entry point

Begin Phase 5.10. Read ADR 0003, `docs/architecture/APPLICATION_WEAVING.md`,
`src/fam_os/applications/contracts/`, the Phase 5.2 native transport, and the
Phase 5.7 provider-isolation pattern. First define provider-neutral screen scene,
capture, target, input primitive, stale-scene, and explicit-unavailability
contracts before selecting X11, Wayland/portal, OCR, or input implementations.
