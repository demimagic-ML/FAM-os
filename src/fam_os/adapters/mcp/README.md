# MCP client adapter ownership

Owns the official MCP SDK lifecycle, local stdio process transport, paginated
discovery, independent allowlisting/effect classification, JSON Schema input and
structured-output validation, bounded normalized results, and mapping into
Application Fabric capability registrations.

MCP annotations are retained only as untrusted adapter data and never determine
whether a tool is read-only or safe. Models and Core never receive the SDK
session. Sampling and elicitation are disabled because the provider port exposes
neither operation. Transport success is not application-action verification.

`ingress/` is the opposite direction: an authenticated, permission-filtered
official-SDK server that exposes only the Core ingress gateway. It has no direct
expert, connector, Supervisor, or verifier access. See
`docs/protocols/MCP_INGRESS_SERVER.md` and ADR 0042.
