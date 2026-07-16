# MCP Application Connector Boundary

## The short answer

FAM_OS will use Model Context Protocol where it provides structured application context or typed tools, but MCP is not the whole application-weaving system.

MCP is a replaceable transport adapter at levels 1 and 2 of the Application Fabric integration ladder. FAM_OS's own application identity, capability, permission, action, result, postcondition, and audit contracts remain canonical.

## Why this boundary exists

MCP standardizes host/client/server communication and capability discovery. Its server primitives include tools, resources, and prompts, with notifications for dynamic changes. That makes it useful for structured local application and tool integration.

MCP does not decide how FAM_OS schedules models, interprets user authority, approves a write, verifies an application postcondition, or audits an action. The official MCP architecture also limits its scope to context exchange rather than dictating how an AI application manages or uses that context.

## Two directions

### FAM_OS as an MCP host/client

FAM_OS connects to an explicitly configured local MCP server exposed by an editor, creative tool, database tool, development service, or FAM connector package.

```text
Application or tool MCP server
          |
   MCP client adapter
          |
MCP-to-capability mapper
          |
Application Capability Registry
          |
FAM Core permission and plan lifecycle
```

The adapter negotiates the protocol and discovers primitives. The mapper translates only approved primitives into provider-neutral Application Fabric capabilities.

### FAM_OS as an MCP server

FAM_OS exposes a local, authenticated, permission-filtered MCP surface so a compatible editor or agent can request selected FAM capabilities.

```text
Compatible application
          |
 local MCP request
          |
FAM MCP ingress adapter
          |
FAM Core admission, approval, execution, verification
          |
permission-filtered result
```

The ingress adapter is a client surface like FAM Shell or the local API. It never calls models, applications, the supervisor, or tools around Core policy.

## Primitive mapping

| MCP concept | FAM_OS treatment |
|---|---|
| Server identity and negotiated version | Connector instance identity and compatibility evidence |
| Resource | Observation capability with explicit scope, sensitivity, freshness, and read permission |
| Tool | Observation or action capability based on effects, never based only on the server's label |
| Tool input schema | Candidate operation input schema, validated again at the Application Fabric boundary |
| Tool result | Untrusted action/observation result requiring normalization and declared postconditions |
| Prompt | Optional connector-supplied interaction template; never authority or trusted policy |
| List-changed notification | Capability-registry refresh signal |
| Progress/log notification | Bounded operation event or telemetry, not proof of success |
| Elicitation | User-interaction request routed through FAM; it cannot grant or replace FAM permission |
| Sampling request | Disabled initially; any future support must use normal expert budgets and model policy |

An MCP tool marked read-only by metadata can help policy, but FAM_OS must independently classify its actual effects. MCP discovery does not equal permission.

## End-to-end action lifecycle

1. The user starts an intent through FAM Shell, a contextual application surface, CLI, local API, or the FAM MCP ingress.
2. Core admits the request with user and session permission context.
3. The Capability Registry returns relevant capabilities from MCP and non-MCP adapters.
4. Core acquires only approved observations.
5. Models and deterministic planners propose an execution plan; they do not invoke MCP directly.
6. Core requests confirmation when required by effect, scope, reversibility, or external consequence.
7. The connector adapter invokes the narrow approved operation.
8. FAM validates the result and checks application or deterministic postconditions.
9. Only the verified outcome is returned as successful, with an audit record identifying the connector, capability, permission, expert, verifier, and resources used.

## When MCP is unavailable

The integration ladder remains:

1. MCP or another native semantic/typed application connector.
2. Deterministic OS, file, D-Bus, portal, CLI, compiler, or converter adapter.
3. Linux AT-SPI accessibility observation and actions.
4. Restricted screen observation and controlled input.

An application can therefore be useful without implementing MCP. Fidelity, context cost, and postcondition strength degrade explicitly as FAM moves down the ladder.

## Security and lifecycle policy

- Start with local MCP servers only. Remote servers remain external services and later require explicit network, trust, identity, and privacy policy.
- Prefer an isolated child process over stdio or an authenticated loopback endpoint according to the connector's lifecycle.
- Pin or negotiate supported protocol versions and retain server identity in audit evidence.
- Treat server descriptions, schemas, resources, prompts, outputs, notifications, and errors as untrusted input.
- Do not copy server credentials into prompts, telemetry, artifacts, or model-visible context.
- Limit roots, environment variables, filesystem access, network access, process lifetime, output size, and concurrency per connector package.
- Do not connect a model directly to a raw MCP session.
- An MCP authorization flow protects transport access; FAM permission separately governs what the user has allowed FAM to observe or do.

## First acceptance demonstration

The Phase 5 demonstration should use all of the following in one verified task:

- One local MCP-backed semantic capability, initially from a code editor or development connector.
- One deterministic tool or OS capability, such as reading files and running tests.
- One unmodified Linux application through AT-SPI or another generic bridge.
- One explicit approval before a write or external effect.
- Deterministic postcondition verification and an audit view.
- A degraded rerun with the MCP server unavailable, proving that FAM can fall back rather than pretending the application disappeared.

## Protocol references

- [Official MCP architecture overview](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP authorization specification, version 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)

The protocol version is an adapter compatibility concern. Domain contracts must not embed one MCP specification version.

## Implementation status

The local client direction is implemented for Phase 5.3 with the official
Python SDK v1 over stdio, independent primitive classification, bounded
discovery/invocation, and registry lifecycle. See
`docs/protocols/MCP_CLIENT_ADAPTER.md` and ADR 0041. The authenticated,
permission-filtered server direction is implemented for Phase 5.4 as a Core
client surface; see `docs/protocols/MCP_INGRESS_SERVER.md` and ADR 0042.
