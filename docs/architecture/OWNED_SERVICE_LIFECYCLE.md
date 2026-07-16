# Ownership-aware unprivileged lifecycle

## Admission path

Production lifecycle calls must go through `OwnedServiceLifecycle`, not directly to a systemd adapter:

```text
SupervisorCallContext
  -> SupervisorAuthorizer.require(capability, service_id)
  -> ServiceOwnershipRegistry claim/lookup
  -> idempotent lifecycle decision
  -> ServiceLifecycle adapter
  -> ServiceStatus
```

The call context contains only stable request, principal, session, and authority references. It does not carry a password, token, secret, or caller-supplied `authenticated` boolean. A concrete transport/authenticator must resolve `authority_ref` behind `SupervisorAuthorizer`.

## Ownership

An owned service binds one FAM service ID and exact `ServiceDefinition` to one principal/session pair. Claims are idempotent only when owner and definition are identical. Reusing the ID with a different definition or principal fails closed.

The registry independently restricts service IDs to the `fam-` namespace. Even a permissive or faulty authorizer cannot turn the lifecycle use case into arbitrary unit control.

`InMemoryServiceOwnershipRegistry` is deterministic test/development storage. A durable registry may replace it through `ServiceOwnershipRegistry`, but it must preserve claim and ownership semantics.

## Idempotence

- Starting an owned active/activating service returns current status without a second adapter start.
- Starting a deactivating service fails rather than racing stop.
- Stopping an inactive, unknown, or already deactivating owned service returns current status without a second adapter stop.
- Status always requires both authorization and ownership.
- Unclaimed service IDs are never forwarded to the lifecycle adapter.

## Scope

The concrete adapter remains `systemd-run --user`/`systemctl --user`. This step adds no system service, root helper, unit persistence, daemon reload, boot enablement, model readiness, resource-policy choice, or recovery loop.
