# Application Fabric Python Contracts

**Contract family:** `fam.applications/v1alpha1`  
**Status:** Python domain contracts and strict `v1alpha1` serialized schemas implemented.

## Boundary

These contracts define what FAM Core can know and request across an application connector boundary. They do not contain VS Code SDK, MCP, D-Bus, AT-SPI, filesystem-command, or screen-control types.

Concrete adapters translate provider data into this vocabulary.

## Identity

- `ApplicationIdentity` identifies an application independently of a running process.
- `ApplicationInstance` identifies one running instance, connector, optional process, and declared workspace scopes.
- Stable identifiers are not titles, window labels, process names, or transport addresses.

## Capability registry

- `CapabilityDescriptor` declares one observation or action, typed input/output schema identities, required authority, confirmation policy, reversibility, and deterministic postconditions.
- `CapabilityRegistryEntry` binds the descriptor to one application instance and connector.
- Observation capabilities require observe authority and cannot claim action postconditions.
- Every action capability declares its reversibility and at least one deterministic postcondition.
- Irreversible actions always require confirmation.

Discovery says what a connector can do. It never says the user has allowed it.

## Observations

`ObservationRequest` carries the Core request, application instance, capability, permission grant, parameters, and optional resource scope.

`ObservationResult` reports an explicit state:

- `observed`
- `denied`
- `unavailable`
- `failed`

Only `observed` results may expose a payload. Payloads are recursively frozen JSON-compatible values so a connector cannot mutate an admitted observation after construction.

Non-observed results carry structured `ApplicationFailure` evidence rather than arbitrary connector error strings. Denied and unavailable statuses must match their failure categories.

## Permission

`PermissionGrant` identifies the user or subject, approved authorities, scope, issue time, optional expiry, and optional revocation. A scope must constrain at least one application, instance, capability, or resource URI; an empty global grant is invalid.

Grant times are timezone-aware and expiry is exclusive. A grant does not remove a capability's confirmation requirement.

## Actions

The action lifecycle is split deliberately:

1. `ActionPreparationRequest` describes the requested operation and expected resource revision.
2. The connector returns an `ActionProposal` containing a concrete preview, preconditions, postconditions, reversibility, and reversal capability where applicable.
3. `ActionConfirmation` records approval or denial by an identified actor under a permission grant.
4. The connector returns an `ActionResult` with explicit terminal status and deterministic `ConditionEvidence`.

A `verified` result requires non-empty passing postcondition evidence and cannot carry an error. A postcondition failure requires failed evidence and is never verified. A failed action may retain a reversal token because execution can have occurred before verification failed.

Non-verified actions carry a structured failure whose category matches denial, precondition, execution, postcondition, or cancellation status. See `FAILURE_DEGRADATION_CONTRACTS.md` and ADR 0017.

Phase 5.11 implements the Core execution envelope that independently verifies
every proposal precondition and postcondition. Provider evidence is never enough
by itself, and non-verified output is withheld. Recoverable actions name a
separate reversal capability and return opaque recovery metadata; undo remains a
new permissioned action rather than an automatic side effect. See
`APPLICATION_ACTION_SAFETY.md` and ADR 0049.

Every execution writes a content-free request audit before provider invocation
and a terminal audit before normal plan advancement. The two additional strict
roots are `fam.application.action-audit-intent/v1alpha1` and
`fam.application.action-audit-record/v1alpha1`.

## Connector transport and registry ports

`ConnectorRegistration` provides:

- Application contract version.
- Connector and application-instance identity.
- Transport kind.
- Adapter protocol identity and version.
- Current capability registry entries.
- An auditable connection time.

`ConnectorTransport` defines registration, observation, action preparation, confirmed execution, and closure. `CapabilityRegistry` defines Core-facing registration and lookup. Both are Python protocols; no concrete socket, MCP session, process, or database is chosen here.

Phase 5.1 implements the dynamic registry with atomic connector-owned replacement,
global collision rejection, instance/capability lookup, availability changes,
immutable revisioned snapshots, and deterministic events. See
`APPLICATION_CAPABILITY_REGISTRY.md` and ADR 0039.

Transport kinds distinguish native local connectors, local MCP, deterministic OS tools, accessibility, and restricted screen/input adapters. They all expose the same domain contracts and enter the same Core-owned action-safety envelope.

## First VS Code profile

The original fake connector exercised two capabilities. Phase 5.9 now implements
the real native connector with this bounded surface:

| Capability | Kind | Authority | Key state or effect | Verification |
|---|---|---|---|---|
| `vscode.editor.active` | Observation | `observe` | Active document URI, language, selection, version, dirty state, visible ranges | Observation status and revision |
| `vscode.editor.selection` | Observation | `observe` | Explicit bounded selected text | Count/text bounds and revision |
| `vscode.diagnostics.active` | Observation | `observe` | Bounded active-document diagnostics | Count/string bounds and revision |
| `vscode.workspace_edit.apply` | Action | `modify` | Previewed reversible workspace edit | Editor-buffer document hash and version |
| `vscode.workspace_edit.undo` | Action | `modify` | Exact token/revision-bound restoration | Restored editor-buffer hash and version |

The action records the full observed version-plus-hash revision as a precondition
and `vscode.workspace_edit.undo` as its reversal capability. The production
extension uses VS Code `WorkspaceEdit` only inside the adapter. See
`VSCODE_SEMANTIC_CONNECTOR.md` and ADR 0047.

Future actions such as saving, running a task, opening a terminal, installing an extension, source control, or making network requests require separate capability identifiers and permission/effect policies.

## Serialized boundary

Application document roots use the self-describing strict JSON envelope and
generated Draft 2020-12 schemas defined in
`SERIALIZED_SCHEMA_COMPATIBILITY.md`. Unknown fields and versions are rejected.
The authenticated local connector transport is implemented by Phase 5.2 and the
VS Code reference SDK interoperates with it in Phase 5.9. `v1alpha1` remains an
exact-match alpha contract rather than a promise of stable external compatibility.
