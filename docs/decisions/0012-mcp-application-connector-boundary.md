# ADR 0012: MCP is an Application Fabric connector protocol

**Status:** Accepted  
**Date:** 2026-07-16

## Context

ADR 0003 established a Universal Application Fabric with native semantic connectors, deterministic OS/tool adapters, accessibility, and restricted vision/input fallback. It did not choose a concrete semantic connector protocol.

MCP provides a useful client/server protocol for capability negotiation and structured tools, resources, prompts, and notifications. Treating MCP as the entire Application Fabric, however, would exclude ordinary applications without servers and would risk confusing protocol discovery or transport authorization with FAM_OS user permission and verified action policy.

## Decision

MCP is a supported, replaceable protocol adapter at levels 1 and 2 of the integration ladder. FAM_OS Application Fabric contracts remain the canonical internal model.

FAM_OS will support two bounded roles:

1. An MCP client adapter maps explicitly configured local-server primitives into Application Capability Registry entries.
2. A permission-filtered local MCP server exposes selected FAM capabilities to compatible applications through the same Core admission, approval, execution, verification, and audit lifecycle as other clients.

Models do not receive raw MCP sessions or direct tool authority. Connector metadata and results are untrusted. MCP transport authorization and FAM user permission are separate checks.

MCP resources map to observations. Tools map to observations or actions according to independently classified effects. Prompts are optional untrusted templates. Notifications refresh capabilities or provide bounded progress; they do not prove success. Elicitation cannot grant FAM permission. Sampling is disabled initially.

The first scope is local. Remote MCP connectivity requires later network, identity, privacy, and trust decisions.

## Consequences

- Applications with MCP support gain structured, lower-context integration.
- Applications without MCP remain usable through native APIs, OS/tool adapters, AT-SPI, or restricted vision/input fallback.
- Phase 2 contracts must carry connector identity, transport metadata, effect classification, schema, scope, postconditions, and compatibility without importing MCP types into Core.
- Phase 5 gains explicit MCP client and server adapter steps.
- Connector packages require sandbox, secret, lifecycle, output, and concurrency limits.
- Protocol version changes remain isolated to adapters.

## Alternatives considered

1. Make MCP the internal Application Fabric bus: rejected because domain policy would depend on an external evolving protocol.
2. Require every application to expose MCP: rejected because universal application coverage needs generic bridges.
3. Avoid MCP and invent a FAM-only connector protocol: rejected because MCP already supplies useful interoperable discovery and invocation semantics.
4. Let models connect directly to MCP servers: rejected because it bypasses deterministic admission, permission, confirmation, verification, and audit boundaries.
5. Expose FAM only as an MCP server: rejected because FAM must also consume structured capabilities from applications and tools.

## Evidence

- `docs/architecture/APPLICATION_WEAVING.md` defines the provider-neutral integration ladder.
- `docs/architecture/MCP_APPLICATION_CONNECTOR.md` defines the mapping and action lifecycle.
- The official MCP architecture documents a host/client/server model, lifecycle negotiation, tools, resources, prompts, and notifications while explicitly limiting MCP's scope to context exchange.
- The MCP 2025-11-25 authorization specification treats transport authorization as an optional protocol concern, supporting the decision to keep it separate from FAM permission policy.
