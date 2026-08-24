# ADR 0220: Natural engineering routing does not override explicit application authority

Status: Accepted

## Context

The Shell natural-engineering adapter originally claimed every local request
that contained exactly one workspace URI. Existing application requests also
carry a workspace URI alongside an explicit application context and capability
set. Once both paths were composed, the broad handler intercepted legacy
workspace-patch and directory actions before the Application Fabric could
evaluate their declared capabilities, returning the generic
`shell.core_unavailable` error.

The deterministic action firewall also treated every sentence beginning with
“use” as a machine effect. The official MCP stdio fixture's conversational
request “Use the MCP bridge” was therefore returned as an immediate terminal
capability refusal. The delegated MCP executor assumed every accepted request
had a durable asynchronous task and tried to reload that terminal refusal as a
task session.

## Decision

An explicit `APPLICATION` context takes routing precedence over the implicit
workspace-based natural-engineering adapter. The natural adapter handles a
Shell request only when there is one exact local workspace, no remote
authority, and no application context. This does not grant the Application
Fabric any natural-engineering authority; it preserves the capability route
the client explicitly selected.

The ambiguous verb “use” is action-shaped only when the remainder names a
recognized machine resource or an exact path. Interface wording without such a
target remains ordinary inference. Other direct machine verbs and all
authority recognition remain unchanged.

A delegated MCP executor must accept an immediate terminal firewall result as
a normal typed outcome. It converts that result directly and does not attempt
snapshot polling or cancellation. This keeps action-shaped delegated requests
fail closed without turning the refusal into an internal error.

## Consequences

- Existing capability-scoped workspace and directory actions are no longer
  stolen by the natural engineering route.
- URI-only Shell requests still reach the two-checkpoint natural engineering
  lifecycle.
- Conversational MCP interface wording can run through ordinary Core inference.
- A real delegated machine action still returns a content-free typed refusal
  and never acquires application authority.
- This source correction requires a new signed installed candidate before it
  can update Phase 30.5 installed evidence.

## Alternatives considered

- Remove the legacy application route: rejected because it provides explicit
  capability-scoped actions that the master engineering loop does not replace.
- Let natural engineering always win when a URI is present: rejected because a
  URI is a parameter, not authority to discard an explicit application scope.
- Make every “use” sentence a machine action: rejected because interface
  language has no concrete effect target.
- Raise on an immediate delegated refusal: rejected because refusal is a valid
  safe terminal result, not executor failure.

## Evidence

- `src/fam_os/adapters/shell/natural_engineering.py`
- `src/fam_os/core/production/action_intent.py`
- `src/fam_os/product/composition/mcp_ingress_executor.py`
- `tests/unit/test_fam_shell_natural_engineering.py`
- `tests/unit/test_action_intent_firewall.py`
- `tests/unit/test_mcp_ingress_executor.py`
- `tests/integration/test_product_mcp_ingress.py`
- `tests/integration/test_product_os_workflows.py`

