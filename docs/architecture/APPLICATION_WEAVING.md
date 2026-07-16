# Application Weaving Architecture

## Product definition

FAM_OS is woven into a PC when the user's existing applications, files, tools, devices, models, and local memory participate in one permissioned intelligence fabric.

FAM is not limited to its own chat window and applications do not all need custom FAM plugins. A native semantic connector is the most efficient integration, but generic operating-system bridges must make useful observation and action possible across ordinary applications.

## User experience

FAM has four access surfaces backed by the same local core:

1. **FAM Shell:** everyday conversation, context, plans, approvals, progress, and results.
2. **FAM Console:** resources, experts, permissions, memory, audit history, diagnostics, and removal.
3. **Application surfaces:** editor, browser, terminal, document, creative-tool, and other contextual integrations.
4. **CLI and local API:** automation, development, and headless operation.

The Shell and Console are clients. They do not own model execution, permissions, scheduling, or verification and can restart without stopping FAM Core.

## Application Fabric

```text
User intent and permitted application context
                    |
                    v
             FAM Shell / API
                    |
                    v
                FAM Core
                    |
                    v
       Application Capability Registry
                    |
        +-----------+-----------+-----------+
        |           |           |           |
   Semantic     OS and tool  Accessibility  Vision/input
   connectors     adapters       bridge       fallback
        |           |           |           |
        +-----------+-----------+-----------+
                    |
                    v
            Existing applications
```

The Capability Registry describes what is available; it does not grant authority. Core combines the originating user intent, current permission grant, reversibility, risk, resource cost, and required verifier before proposing or executing an action.

## Integration ladder

FAM selects the highest-fidelity available integration for each application and action.

| Level | Mechanism | Typical state and actions | Properties |
|---|---|---|---|
| 1 | Native semantic connector or typed application API, including MCP-backed connectors | Documents, selections, symbols, timelines, layers, domain commands | Lowest context cost and strongest postconditions |
| 2 | OS and deterministic tool interfaces | Files, MIME operations, D-Bus, desktop portals, CLIs, compilers, converters | Broad, exact, and easy to verify |
| 3 | Linux accessibility bridge | Windows, controls, text fields, menus, focus, accessible actions | Works with many unmodified desktop applications |
| 4 | Screen observation and controlled input | Pixels, pointer, keyboard, custom canvases | Expensive and fragile; explicit policy and postconditions required |

FAM may combine levels. It can read an editor through a semantic connector, run tests through a deterministic tool adapter, and use accessibility to operate a dialog.

## Where MCP fits

MCP is one protocol for carrying structured context and typed operations into or out of the Application Fabric. It is not the Application Fabric itself.

- FAM_OS can act as an MCP client/host to consume approved tools and resources from local application or tool servers.
- FAM_OS can expose a permission-filtered local MCP server so compatible applications can request selected FAM capabilities.
- MCP tools and resources are normalized into FAM application capabilities before Core sees them.
- MCP discovery and transport authorization never grant FAM observation or action authority.
- Models never receive a raw MCP session or bypass the normal plan, confirmation, postcondition, and audit lifecycle.
- Applications without MCP continue through native APIs, deterministic OS/tool interfaces, accessibility, or the restricted screen/input fallback.

See `MCP_APPLICATION_CONNECTOR.md` and ADR 0012 for the mapping and security boundary.

## Capability model

Every observed application capability must eventually have versioned fields for:

- Application and instance identity.
- Capability and operation identity.
- Observation versus action classification.
- Input and output schemas.
- Read, propose, modify, and execute authority.
- Application, document, project, and time scope.
- Reversible, compensatable, or irreversible classification.
- Required confirmation level.
- Preconditions and postconditions.
- Required verifier or acceptance policy.
- Trust, latency, resource, and privacy cost.

Capabilities are discovered dynamically and can disappear when an application closes, a document changes, permission expires, or an adapter fails.

## Observation and action are separate

Permission to observe an application never implies permission to modify it. The standard lifecycle is:

1. Admit the user's intent and permission context.
2. Discover relevant application capabilities.
3. Acquire only authorized observations.
4. Build an execution plan using models and deterministic tools.
5. Present risky or externally consequential actions for approval.
6. Execute through the narrowest capable adapter.
7. Check postconditions with application state or a deterministic verifier.
8. Return a verified result and append an audit event.

Failed postconditions must not be presented as successful actions. Where possible, modifications are previewed, transactional, undoable, or paired with a compensating action.

## Local optimization

Application weaving reduces rather than increases model cost when structured state is preferred over screenshots:

- The resident kernel receives compact intent and capability summaries.
- Foreground-application context is retrieved only with permission and only when relevant.
- Deterministic operations replace token-heavy imitation of tools.
- The scheduler preloads experts associated with the current workflow and evicts unrelated experts.
- Vision is a fallback instead of the default desktop representation.
- Verification uses application postconditions, files, tests, compilers, and schemas.

## Boundaries

- Application adapters never decide their own permissions.
- Models never receive unrestricted desktop, filesystem, input, or network authority.
- The privileged supervisor enforces approved process and resource operations but interprets no natural language.
- Anti-cheat, DRM, security boundaries, and application policies are not bypassed.
- Unsupported or inaccessible application behavior degrades to suggestion or user-guided execution.

## Initial acceptance demonstration

The first Application Fabric milestone must demonstrate one cross-application task that:

1. Begins in FAM Shell.
2. Observes at least one unmodified Linux application through a generic bridge.
3. Uses at least one deterministic OS or tool capability.
4. Uses one native semantic connector backed by local MCP where the chosen application supports it.
5. Requires an explicit write or external-action approval.
6. Verifies postconditions.
7. Shows the user which capabilities, experts, permissions, and resources were used.
8. Repeats in a declared reduced-fidelity mode when the MCP connector is unavailable.

## Implementation status

Dynamic registry, authenticated local connector transport, bidirectional MCP
adapters, privacy-bounded Linux discovery, deterministic OS/tool adapters,
bounded AT-SPI, the unprivileged FAM Shell, and the first native VS Code semantic
connector are implemented through Phase 5.9. Phase 5.10 adds a last-resort,
active-window-only X11 screen/input adapter with bounded PNG capture, exact-scene
revalidation, and only one click or an allowlisted key chord. The editor
connector separates metadata/text authorities and provides confirmed revision-bound edits with
bounded exact reversal. Phase 5.11 now routes every action level through one
Core-owned execution envelope with exact proposal/approval/grant binding,
trusted pre/postcondition verification, replay protection, content-free durable
auditing, output withholding, and explicit recovery metadata. See
`docs/protocols/LINUX_APPLICATION_DISCOVERY.md`,
`docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md`,
`docs/protocols/LINUX_ACCESSIBILITY_BRIDGE.md`, `docs/protocols/FAM_SHELL_MVP.md`,
`docs/protocols/VSCODE_SEMANTIC_CONNECTOR.md`,
`docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md`,
`docs/protocols/APPLICATION_ACTION_SAFETY.md`. Phase 5.12 completes the first
measured vertical user flow through the real Shell socket, an unmodified Linux
application, deterministic file/test adapters, official-SDK MCP, the live VS
Code extension, explicit edit approval, trusted verification, and an
MCP-unavailable successful rerun. See
`docs/operations/CROSS_APPLICATION_ACCEPTANCE.md` and ADRs 0043-0050.
