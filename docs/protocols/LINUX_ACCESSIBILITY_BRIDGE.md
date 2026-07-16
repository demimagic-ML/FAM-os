# Linux Accessibility Bridge

## Purpose

Phase 5.7 supplies Application Fabric level-3 access to unmodified Linux
applications through AT-SPI. It is a reduced-fidelity semantic bridge used only
when a native connector or deterministic OS capability is unavailable or
insufficient. AT-SPI remains an adapter detail; Core sees bounded application
observations and separately prepared actions.

## Provider boundary

`AccessibilityProvider` is the narrow port between the bridge and a desktop
accessibility implementation. `GiAtspiProvider` is the Linux implementation. It
loads GI dynamically, discovers only top-level application roots, normalizes
provider values, and returns empty or unavailable results on provider failure.
No GI object crosses into Application Fabric contracts.

The bridge does not spawn a process, inherit a shell, or use screen pixels and
input injection.

## Bounded observations

`AccessibilityBridgePolicy` bounds:

- total nodes;
- traversal depth;
- text characters read per node;
- exposed actions per node; and
- the exact action-name allowlist.

Traversal is breadth-first and never queues more objects than the remaining node
budget. A snapshot reports `truncated=True` when node, depth, child, text, or
queue limits omit data. Text is not read from the provider unless the caller
explicitly requests it.
Failure to find exactly one top-level root for a requested process returns an
empty `accessibility.unavailable` snapshot instead of guessing.

Password roles are protected at the concrete provider and contract boundary.
Their name, description, text, and actions are absent. Role, structural path,
and non-content state may remain visible so the caller can understand why the
node cannot be used.

## Object identity and actions

An observed object reference contains the application process ID, its child
index path from the application root, and a SHA-256 fingerprint of stable
observable identity fields. The short reference ID is display/correlation data;
the full digest is used for revalidation.

Action execution is deliberately split:

1. `prepare_action` resolves the path again, verifies the full fingerprint,
   rejects protected objects, and selects only an action that was visible within
   the configured allowlist and action bound.
2. Core permission and confirmation policy decides whether the proposal may run.
3. `perform_action` resolves and revalidates the object a second time, requires
   the same index and exact action name, and then invokes the provider action.

Supported default action names are `activate`, `click`, `collapse`, `expand`,
`press`, `select`, `show menu`, and `toggle`. There is no generic action index or
arbitrary AT-SPI method surface.

The returned `AccessibilityActionEvidence` proves only that invocation was
attempted and records pre/post fingerprints. It is not proof of the user's
intended result. The connector declaration therefore marks actions irreversible,
always-confirmed, and subject to the separate
`accessibility.action.poststate` deterministic postcondition.

## Permissions and privacy

The connector registration is scoped to one process ID. Observation authority
does not imply execution authority. Application identity, process scope,
capability grant, and optional text access must be checked by Core before calling
the bridge. Window discovery continues to omit titles by default; this bridge
does not convert general accessibility content into ambient context.

AT-SPI is a same-session semantic interface, not a security sandbox. A malicious
or buggy application can publish misleading roles, names, states, or actions.
All values are untrusted evidence and all externally visible actions remain under
Core approval, postcondition, and audit policy.

## Live evidence

The live integration test attaches only when the current session exposes AT-SPI.
It selects an unambiguous application process and reads at most 64 nodes, depth
4, and eight actions per node while requesting and reading no text. It invokes
no action and performs no desktop mutation. When GI or the
AT-SPI bus is absent, the test and runtime degrade explicitly.
