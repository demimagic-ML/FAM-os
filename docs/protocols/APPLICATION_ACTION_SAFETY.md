# Application Action Safety Protocol

## Scope

Phase 5.11 defines the Core-owned safety envelope shared by native semantic,
MCP, deterministic OS/tool, accessibility, and restricted screen/input actions.
Adapters may prepare and invoke actions, but they do not authorize themselves
and their returned evidence is not trusted verification.

## Required execution chain

Core executes an application action only when all of these bindings still hold:

1. The routed request is the request admitted into the current plan instance.
2. The current plan revision points to one `execute_action` step and its single
   capability is currently registered for the exact application instance.
3. The unexpired grant covers the principal, application, instance, capability,
   resource, and capability-required execution authority.
4. The proposal matches the registered reversibility, confirmation policy, and
   deterministic postcondition identifiers.
5. The plan contains exactly one prior proposal reference and one prior approval
   reference for that proposal's capability and grant.
6. The approval was made by the admitted principal, after the proposal event and
   no later than the trusted Core time.
7. Every declared trusted precondition passes immediately before invocation.

Confirmation IDs are reserved atomically before provider invocation. Replaying
one never calls the provider.

## Verification and release

The provider is invoked at most once. Its `ActionResult` must name the approved
proposal, agree with the expected before revision, and obey the proposal's
recovery classification. Core then runs the declared postconditions through a
trusted verifier port.

Provider-supplied postcondition evidence cannot make an action verified. Core
replaces it with verifier-owned evidence. Output is released only when every
declared postcondition passes and required recovery metadata is present.
Otherwise output is empty, the execution step follows its failed edge, and a
safe structured failure is returned without provider exceptions or raw values.

## Recovery semantics

Reversible and compensatable proposals must name a separate recovery capability.
A verified recoverable action must return an opaque reversal token. When the
provider was invoked but verification or terminal auditing fails, Core preserves
the token and marks compensation required where possible.

This phase records recovery metadata; it does not execute undo automatically.
Undo or compensation is a new permissioned, proposed, confirmed, verified, and
audited action through its declared capability.

Irreversible actions cannot expose recovery metadata and always require explicit
confirmation.

## Required audit

A privacy-bounded request event must be durably appended before mutation. A
terminal event must be appended before normal plan advancement. Both are linked
to the operation, request, plan, principal, session, application, instance,
capability, grant, proposal, and confirmation.

Audit events contain identifiers, resource URI hashes, condition identifiers,
status, recovery availability, and safe failure codes. They exclude prompts,
previews, parameters, raw resource URIs, provider output, reversal tokens, and
failure detail.

The reference `ApplicationJsonlAuditSink` uses private user-owned files,
exclusive append locking, canonical records, duplicate-event rejection, `fsync`,
and a SHA-256 predecessor chain. It is tamper-evident, not a signature or defense
against deletion by the owning user.

If the request audit is unavailable, no provider call occurs. If the terminal
audit fails after an action may have occurred, Core withholds output, records a
safe audit-unavailable failure in lifecycle state, and preserves recovery
metadata. It never falsely reports verified success.

## Serialized contracts

- `fam.application.action-audit-intent/v1alpha1`
- `fam.application.action-audit-record/v1alpha1`

Both use the strict self-describing application contract envelope. The record
digest is calculated over the canonical record content excluding its own digest.

## Boundaries

- No model, Shell client, adapter, or MCP server can bypass Core execution.
- No condition verifier receives authority to mutate the application.
- Audit durability does not prove the application's semantic postcondition.
- Recovery metadata does not imply recovery succeeded.
- Phase 8.7 will package application-action verifiers and strengthen their trust
  deployment; this phase establishes the mandatory Core seam and lifecycle.
