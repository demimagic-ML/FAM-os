# ADR 0121: MCP ingress is a permission-filtered Core client

**Status:** Accepted  
**Date:** 2026-07-17

## Context

FAM_OS already had an SDK-neutral authenticated MCP ingress engine and an
official MCP SDK server, but neither was reachable from the product service.
Running those components directly inside each application would duplicate Core
state, bypass durable admission, or let a bridge call a model or connector
without the normal result policy.

MCP applications normally start a stdio process, while FAM Core is a persistent
owner service. The two lifecycles therefore need a local bridge without moving
authority or execution into the short-lived stdio process.

## Decision

The product service owns an owner-private `mcp-ingress.sock` endpoint. Ingress
is disabled when `mcp-ingress.json` is absent or explicitly disabled. Enabling
it requires an owner-controlled mode-0600 configuration with an explicit client
and capability allowlist.

The installed command `fam-os mcp serve --client-id ID` is only an official MCP
stdio bridge. It connects to the running service, obtains a one-time bootstrap
credential after Unix peer-UID validation, opens a second authenticated
session, and proxies bounded typed tool-list and tool-call messages. Raw tokens
are never persisted and are consumed by the first session authentication.

The daemon maps each configured client to a durable expiring
`RequestAuthorityGrant`. Tool discovery and every call recheck that grant.
Calls then enter `LifecycleCoreIngressGateway`, durable request admission and
replay protection, and the same `ProductionTaskGateway` used by Shell and
Console. Delegated tasks retain the authenticated client principal and session;
they are not rewritten as `local-owner`.

The initial ingress surface exposes only `fam.ask` and `fam.ask.verified`.
Neither accepts application context or mutation capabilities. The verified
variant withholds model output unless normal Core verification produces a
verified result. Expanding the MCP surface requires another explicit
capability mapping and must not grant connector authority implicitly.

## Consequences

- The MCP stdio process cannot access Ollama, a connector, or Core storage
  directly.
- Permission filtering and replay protection survive client-process churn and
  are authoritative in the daemon.
- A same-user process can reach other owner endpoints such as FAM Shell; Unix
  peer credentials do not establish cryptographic application identity. The
  MCP boundary therefore protects against accidental capability exposure and
  non-owner users, while hostile same-user process isolation remains a broader
  Linux/session-hardening concern.
- Application actions remain on the Application Fabric approval and
  postcondition path rather than being smuggled through generic MCP prompts.
