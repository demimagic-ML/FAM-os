# Dynamic Application Capability Registry

The Phase 5.1 registry owns dynamic connector registrations independently of
transport. A registration is one atomic ownership unit. Registering a new value
for the same connector replaces all of that connector's previous indexes in one
commit. Removing a connector removes every owned capability.

Global entry IDs, application-instance ownership, and `(instance, capability)`
pairs cannot collide across connectors. Collision or event-construction failure
leaves registrations, indexes, revision, and events unchanged.

Readers receive deterministically sorted immutable tuples or a revisioned
snapshot. Capability availability changes replace frozen registration/entry
objects and emit a typed event; idempotent changes emit nothing. Events have
strictly increasing revisions and support replay after a caller's last revision.

The registry imports no MCP, VS Code, D-Bus, accessibility, screen-input, Core,
or adapter implementation. Those transports register the same provider-neutral
contracts in later steps.
