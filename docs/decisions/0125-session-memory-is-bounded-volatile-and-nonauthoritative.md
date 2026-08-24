# ADR 0125: Session memory is bounded, volatile, and nonauthoritative

**Status:** Accepted  
**Date:** 2026-07-17

## Context

The Phase 10 memory package had a digest-verifying, scope-checked ephemeral
store, but the production graph had no callers. Every Shell and Console request
therefore behaved as an isolated chatbot turn. Simply appending chat history to
the durable request would make ephemeral memory persistent, duplicate sensitive
content in storage, and permit old model text to be mistaken for authority,
application observation, citation, or verification.

The user also needs predictable boundaries: one Console login must not see
another login's conversation, a terminal session must keep a stable identity
across its requests, MCP cannot select another client's scope, and stopping the
service must erase the default memory.

## Decision

The product composes one `ProductionSessionMemory` instance per service process.
It wraps `BoundedEphemeralMemoryStore` and never writes its conversation window
to SQLite or another persistent store.

The memory scope comes from the authenticated ingress:

- a Shell controller creates one random memory-session ID for its lifetime;
- Console uses its server-issued HttpOnly session ID and ignores any client
  attempt to choose a memory scope;
- MCP uses the already authenticated principal and session supplied to Core.

Each admitted request records a bounded user turn after durable admission. Core
records an assistant turn only after final-result policy releases successful
content. Failed and withheld results add no assistant content. Candidate,
verifier, or connector output cannot write directly to memory.

Before inference, Core retrieves only prior records matching the exact owner and
session. It excludes the current request and appends the result to the user
message under an explicit instruction that the content is untrusted
conversation—not authority, verified fact, application observation, citation,
or permission to act. Immutable plans, capabilities, approval, and verification
remain unchanged.

The defaults are 512 records, 4 MiB total, 32 KiB per turn, 16 context records,
64 KiB injected context, and an eight-hour TTL. Capacity removes the oldest
record through the memory deletion contract. The entire store disappears on
service stop or restart. Persistent document and preference memory remain
disabled until separately approved and implemented in later Phase 20 steps.

## Consequences

- Ordinary local conversations can carry context without turning default memory
  into hidden persistent storage.
- Session identity is security-relevant and is derived at trusted ingress
  boundaries rather than from Console request JSON or MCP model text.
- A restart intentionally forgets the conversation; this is correct for 20.1,
  not a recovery defect.
- Memory can influence generation but cannot broaden a plan, capability,
  permission, acceptance contract, or result assurance.
- Later persistent memory must use a separate opt-in storage, grant, expiry,
  inspection, and deletion path rather than changing these defaults silently.

