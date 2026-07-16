# Core routing lifecycle

## Invariant

Only an admitted request can enter Core routing. Routing may classify work, but
it cannot learn transport identity, widen permission scope, drop required
capabilities, reorder their evidence, or release output.

```text
AdmittedTaskRequest
  -> permission-expiry check
  -> RoutingRequest(request ID, prompt, effective capabilities only)
  -> provider-neutral TaskRouter port
  -> exact typed RoutingResult validation
  -> RoutedTaskRequest or structured Core failure
```

## Privacy and authority boundary

`CoreRoutingService` constructs the routing request itself. The router receives:

- request ID;
- prompt;
- effective required capabilities from the admitted permission context.

It does not receive principal ID, session ID, authority reference, the authority's
unused capabilities, admission internals, or credentials.

Permission expiry is checked immediately before the router call. An expired
permission returns `routing.permission_expired` and the router is not invoked.
Phase 4.5 will generalize this recheck to approval and action transitions.

## Result binding

`RoutedTaskRequest` retains the complete admitted request and one typed
`RoutingResult`. Its construction requires the decision's capability tuple to
equal the effective permission tuple exactly. Widening, omission, substitution,
and reordering all fail.

The existing routing result has no caller-controlled request identity. Core binds
it to the admitted request in `RoutedTaskRequest` and exposes that request ID as
derived evidence. A router cannot choose a different request identity.

Routing contracts now require exact current version, bounded identifiers and
prompt, no more than 64 strict unique capability IDs, finite confidence in
`[0, 1]`, and a one-line reason of at most 500 characters.

## Failure mapping

- expired permission: `routing.permission_expired`, permission denied, user action;
- router exception: `routing.provider_unavailable`, unavailable, backoff;
- wrong result type or capability mismatch: `routing.invalid_result`,
  incompatible, never retry automatically.

All failures use fixed safe messages and `FailureComponent.ROUTING`. Raw provider
exceptions, model output, filesystem paths, and parsing details never enter the
Core failure envelope.

## Dependency boundary

The lifecycle depends on admitted-request/Core contracts plus
`fam_os.routing.contracts` and `fam_os.routing.ports.TaskRouter`. It does not
import the model router, inference runtime, Ollama, applications, experts,
Scheduler, Supervisor, verifier, memory, desktop, or OS adapters.

A deployment may inject `ModelTaskRouter`, a deterministic router, or a test fake
through the same port. The lifecycle behavior remains unchanged.

## Current limitations

- This step selects and validates a route but does not construct or execute a plan.
- Retry/backoff execution belongs to later Phase 4 transitions.
- Route fitness and model evaluation remain routing-component concerns.
- Permission expiry is not yet represented as a persisted lifecycle event.
- Routing lifecycle contracts remain internal Python objects until a process
  transport needs a new serialized root.

## Evidence

Tests prove least-data routing input, exact capability preservation, widening/
drop/reorder rejection, permission-expiry short circuit, safe provider failure,
wrong-result rejection, strict routing contracts, and unambiguous outcomes. An
architecture test forbids inference/runtime/external-boundary imports.
