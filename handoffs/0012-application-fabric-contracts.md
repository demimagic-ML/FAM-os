# Handoff 0012: Application Fabric contracts

**Date:** 2026-07-16  
**Plan step:** Phase 2.4, 2.5, and 2.9  
**Status:** Complete  
**Previous handoff:** `0011-full-hardware-and-mcp-plan.md`

## Objective

Implement the first provider-neutral Application Fabric Python contracts before prototyping the VS Code extension, then prove that the contracts support high-fidelity observation and a reversible, confirmed, deterministically verified workspace-edit workflow without importing VS Code or MCP implementation types.

## Scope completed

- Added stable application and running-instance identity.
- Added observation/action capability descriptors and instance-bound capability registry entries.
- Required every action capability to declare reversibility and deterministic postconditions.
- Required irreversible actions to use an always-confirm policy.
- Added scoped, expiring, and revocable permission grants with timezone-aware audit times.
- Added immutable observation requests and explicit observed, denied, unavailable, and failed results.
- Prevented denied or failed observations from exposing connector payload.
- Added recursively frozen JSON-compatible connector payloads.
- Split action preparation, preview, confirmation, execution result, and postcondition evidence into separate types.
- Required reversible proposals to name a reversal capability.
- Prevented an action result from claiming verified success without passing deterministic evidence.
- Added versioned connector registration with protocol identity/version and transport kind.
- Added provider-neutral `ConnectorTransport` and `CapabilityRegistry` ports.
- Added connector lifecycle event contracts for capability changes, instance changes, and closure.
- Added a fake VS Code connector and registry exercising registration, active-editor observation, reversible workspace-edit preparation, explicit approval, execution, and document-hash/workspace-test evidence.
- Documented the `fam.applications/v1alpha1` Python contract family and first VS Code profile.
- Added ADR 0013 for the provider-neutral Application Fabric boundary.
- Marked Master Plan steps 2.4, 2.5, and 2.9 complete.

## Explicitly not completed

- No VS Code extension, extension manifest, TypeScript package, VS Code SDK dependency, or `WorkspaceEdit` adapter was added.
- No MCP SDK, MCP client, MCP server, or MCP wire type was added.
- No Unix socket, stdio, Streamable HTTP, WebSocket, authentication, or connector-process lifecycle implementation was added.
- No production capability-registry storage or discovery implementation was added.
- No serialized JSON Schema, decoder, encoder, compatibility migration, or unknown-field policy was added.
- Permission-scope evaluation and action-result-to-approved-proposal matching remain Core policy work.
- No real file, editor, terminal, application, service, model, or machine setting was changed.

## Architecture and decisions

ADR 0013 establishes `fam_os.applications` as the owner of provider-neutral application identity, capability, authority, observation, prepared action, confirmation, verification-evidence, result, registration, and connector-port language.

The types use frozen, slotted standard-library dataclasses and enums. Connector payloads admit only recursively frozen JSON-compatible values. This preserves the provider-neutral approach of ADR 0002 while providing a clear future serialization boundary.

Capability discovery, permission, confirmation, execution, and verification remain separate. A registered capability is not an authority grant. A permission grant does not remove confirmation. A connector saying an operation completed is not enough for a verified result.

The fake VS Code workflow is deliberately shaped around useful semantics without importing provider objects. `vscode.editor.active` observes a document URI, language, selection, and revision. `vscode.workspace_edit.apply` prepares a preview, checks document version, records `vscode.workspace_edit.undo`, and requires document-hash and workspace-test evidence.

`APPLICATION_CONTRACT_VERSION` is `fam.applications/v1alpha1`. This versions the current Python contract family but is not a stable cross-process wire schema. Phase 2.7 owns serialization and compatibility.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/identity.py` | Stable application and running-instance identity |
| `src/fam_os/applications/capabilities.py` | Capability descriptors, safety invariants, and registry entries |
| `src/fam_os/applications/permissions.py` | Scoped and time-bounded permission grants |
| `src/fam_os/applications/observations.py` | Immutable observation request/result contracts |
| `src/fam_os/applications/actions.py` | Preparation, proposals, confirmation, reversibility, conditions, evidence, and results |
| `src/fam_os/applications/connectors.py` | Versioned registration, events, connector transport, and registry ports |
| `src/fam_os/applications/payloads.py` | Recursively frozen JSON-compatible payload boundary |
| `src/fam_os/applications/policy.py` | Capability, authority, confirmation, and reversibility enums |
| `src/fam_os/applications/identifiers.py` | Stable identifier and scoped-string validation |
| `src/fam_os/applications/timestamps.py` | Timezone-aware audit-time validation |
| `src/fam_os/applications/__init__.py` | Public Application Fabric exports |
| `tests/unit/test_application_identity_capabilities.py` | Identity and capability construction invariants |
| `tests/unit/test_application_permissions_actions.py` | Permission, payload, observation, confirmation, and action-result invariants |
| `tests/unit/test_application_connector_contracts.py` | Complete fake VS Code connector and registry workflow |
| `docs/protocols/APPLICATION_CONTRACTS.md` | Contract family, lifecycle, invariants, and VS Code profile |
| `docs/decisions/0013-application-fabric-python-contracts.md` | Provider-neutral contract decision |
| `src/fam_os/applications/README.md` | Component implementation map and entry point |
| `MASTER_PLAN.md` | VS Code vertical slice, completed steps, evidence, and next step |
| `README.md` | Current implementation and next-step status |
| `handoffs/README.md` | Handoff sequence update |
| `handoffs/0012-application-fabric-contracts.md` | This implementation handoff |

## Public interfaces

- `APPLICATION_CONTRACT_VERSION`
- `ApplicationIdentity`
- `ApplicationInstance`
- `CapabilityKind`
- `ApplicationAuthority`
- `ConfirmationPolicy`
- `Reversibility`
- `CapabilityDescriptor`
- `CapabilityRegistryEntry`
- `PermissionScope`
- `PermissionGrant`
- `ObservationStatus`
- `ObservationRequest`
- `ObservationResult`
- `ConditionRequirement`
- `ConditionEvidence`
- `ActionPreparationRequest`
- `ActionProposal`
- `ConfirmationDecision`
- `ActionConfirmation`
- `ActionStatus`
- `ActionResult`
- `ConnectorTransportKind`
- `ConnectorRegistration`
- `ConnectorEventKind`
- `ConnectorEvent`
- `ConnectorTransport`
- `CapabilityRegistry`

No interface above contains a concrete VS Code, MCP, Linux desktop, or persistence type.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/unit -p 'test_application_*.py' -v
```

Result: all 18 focused Application Fabric tests passed in 0.001 seconds; 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: all 123 FAM_OS tests passed in 0.030 seconds; 0 failures. The previous suite contained 105 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "(^|\s)(import|from)\s+(vscode|mcp)|WorkspaceEdit" \
  src/fam_os/applications --glob '*.py'
```

Result: no provider imports or provider API types were found. `MCP_LOCAL` remains only a provider-neutral transport-kind value.

All implementation files remain below 200 lines; the largest focused test file is 265 lines. No function was expanded into a cross-component orchestrator.

## Evidence and artifacts

- `docs/protocols/APPLICATION_CONTRACTS.md`
- `docs/decisions/0013-application-fabric-python-contracts.md`
- `tests/unit/test_application_connector_contracts.py`
- `tests/unit/test_application_identity_capabilities.py`
- `tests/unit/test_application_permissions_actions.py`
- `docs/architecture/APPLICATION_WEAVING.md`
- `docs/architecture/MCP_APPLICATION_CONNECTOR.md`

## Known limitations and risks

- `v1alpha1` is a Python contract marker, not a stable wire schema.
- Recursive payload freezing validates JSON-compatible structure but does not validate capability-specific schemas; Phase 2.7 must do so at decoding boundaries.
- A mapping proxy requires explicit serialization and must not be sent directly through a transport implementation.
- Permission grants record scope and active time but Core policy does not yet evaluate a request against those selectors.
- The connector result carries evidence, but Phase 4 must match every evidence identifier and verifier against the exact approved proposal before releasing success.
- Connector identity is declared but not authenticated yet.
- Registry entries are not persisted, refreshed, expired, or reconciled because the production registry is Phase 5.1.
- Revision preconditions are represented but not executed against a real editor.
- Reversal capability and token are represented but undo behavior is not implemented.
- The fake connector proves domain composition, not VS Code API behavior or security.

## Operational notes

This change is Python contracts, documentation, and in-memory tests only. It opened no socket, started no connector, touched no editor, changed no model, and performed no privileged operation.

## Recommended next entry point

Complete the remaining Phase 2.1 contract family: inventory the existing Core request, route, execution, and final-result types; add a provider-neutral execution-plan contract; and decide version-family boundaries without changing Phase 1 behavior. Then implement Phase 2.2 hardware/resource schemas. Do not begin the real VS Code extension until Phase 2.7 supplies serialized schemas and Phase 5.2 defines authenticated local transport behavior.
