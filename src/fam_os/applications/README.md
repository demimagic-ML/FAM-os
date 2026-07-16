# Application Fabric ownership

Owns application capability identity, discovery, observations, action proposals, permission context, connector coordination, and application postcondition contracts.

Native semantic connectors are the preferred integration, not the only integration. Concrete Linux desktop, accessibility, D-Bus, application API, vision, and input mechanisms belong in separate adapter modules. This component never grants itself authority or bypasses confirmation and verification policy.

MCP is one replaceable connector transport. An MCP adapter may map local-server tools and resources into these contracts or expose selected FAM capabilities to another application, but MCP protocol objects must not become the domain model. Discovery and transport authorization do not grant observation or action permission, and models never receive raw connector sessions.

See `docs/architecture/MCP_APPLICATION_CONNECTOR.md` and ADR 0012.

## Implemented contract modules

- `identity.py`: stable application and running-instance identity.
- `capabilities.py`: observation/action descriptors and registry entries.
- `permissions.py`: scoped, expiring, and revocable permission grants.
- `observations.py`: immutable observation requests and explicit results.
- `actions.py`: prepared previews, confirmation, reversibility, postconditions, evidence, and results.
- `connectors.py`: versioned registration plus connector-transport and registry ports.
- `manifest.py`: versioned static connector package declaration, protocol support, requested authorities, and maximum capability surface.
- `payloads.py`: recursively frozen JSON-compatible connector payloads.
- `failures.py`: structured, safe, retry-aware application failures aligned with observation/action status.
- `discovery.py`: provider-neutral installed application, launch metadata,
  process, window, focus, and explicit discovery-issue snapshots.
- `registry.py`: atomic connector-owned dynamic capability registration and revisioned snapshots.
- `transport/`: peer-authenticated Unix IPC, bounded framing, typed contract codec,
  correlation, cancellation, registry dispatch, and disconnect cleanup.

The first tested profile is a fake VS Code connector that observes the active editor and applies a reversible, confirmed workspace edit only with document-hash and workspace-test evidence. Read `docs/protocols/APPLICATION_CONTRACTS.md` and ADR 0013 before implementing a concrete connector.

Static `ConnectorManifest` and live `ConnectorRegistration` are intentionally different lifecycles. A package declaration grants no permission and creates no running instance. Read `docs/protocols/MANIFEST_CONTRACTS.md` and ADR 0016 for the package boundary.

The local transport authenticates the current Unix user with kernel peer
credentials, not a connector package. Read
`docs/protocols/AUTHENTICATED_LOCAL_APPLICATION_TRANSPORT.md` and ADR 0040
before implementing a connector process or MCP adapter.

The consuming/local-client MCP direction is now implemented under
`adapters/mcp/`. It produces normal connector registrations and bounded
untrusted outcomes; it does not add MCP types here. See
`docs/protocols/MCP_CLIENT_ADAPTER.md` and ADR 0041.
