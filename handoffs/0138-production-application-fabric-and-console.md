# Handoff 0138: Production Application Fabric and Console

**Date:** 2026-07-17  
**Plan steps:** Phase 18.6 application portion; Phase 19.1–19.5, 19.8–19.9;
Phase 19.6 and 19.10 partial  
**Status:** In progress  
**Previous handoff:** `0137-signed-live-expert-catalog-and-responsive-workers.md`

## Scope completed

- Started the owner-private Application Fabric Unix socket from
  `LocalProductService` and connected it to the same durable Core used by Shell
  and Console.
- Composed the live capability registry, authenticated connector broker, Linux
  discovery, durable permission/action services, configured local transports,
  and independent application postcondition verifier.
- Replaced fixed application prompt handling with deterministic,
  capability-driven resolution and plan compilation. Read-only prompts cannot
  accidentally acquire mutation capabilities, and plans contain at most one
  action.
- Added owner-private `os-tools.json` composition for bounded scoped file reads
  and fixed executable/argument project commands. Model output cannot alter the
  command line or working directory.
- Composed allowlisted outbound MCP clients. Provider assertions remain
  insufficient for verified action status without a Core verifier.
- Added an atomic VSIX packaging and connector install, status, update, and
  remove lifecycle. Failed update staging preserves the installed version.
- Added VS Code active-editor, selection, diagnostics, revision-bound apply,
  undo, and disk-persisted save capabilities. Core recomputes the saved file
  digest through an `O_NOFOLLOW` regular-file read.
- Added durable Console task, snapshot, SSE, decision, and cancellation APIs.
  Bootstrap credentials exchange into HttpOnly SameSite sessions, and
  mutations require a matching Origin plus CSRF token.
- Rebuilt Console around the fabric execution spine and made plain terminal
  input submit and follow natural-language tasks. Slash commands retain direct
  control and `ask` remains a compatibility alias.
- Made approval-time cancellation revoke the permission grant, terminalize
  state, and prevent action invocation. Worker exceptions now terminalize
  durably instead of creating restart loops.

## Corrected integration defect

The first real project-command workflow failed before approval because every OS
capability inherited the project directory as a required resource URI. That is
correct for file observation but wrong for a fixed project command whose
executable, arguments, and working directory are already bound by
owner-controlled configuration. Observation entries remain directory-scoped;
command entries are scoped by application instance and exact capability. The
real summary and approved `/bin/true` project-test workflow now passes.

## Validation

- 31 focused Phase 19 Python tests pass, covering the private fabric,
  observation, action safety, cancellation, deterministic OS workflows,
  Console HTTP/session controls, planner/resolver, MCP client composition,
  connector lifecycle, and Shell.
- VS Code TypeScript compilation passes.
- Seven connector unit tests, native transport integration, and ten connector
  schema validations pass.
- The most recent whole-project run before the deterministic OS-tool addition
  passed 904 tests with three declared skips. The full suite must be rerun after
  the remaining Phase 19 composition work.

## Remaining work

- Phase 18.6: production-select declared Python, retrieval, mathematics, and
  media verifiers. Application and deterministic OS postconditions are wired.
- Phase 19.6: compose permission-filtered MCP ingress into the product service;
  outbound allowlisted MCP clients are already live.
- Phase 19.7: expose explicit disabled-by-default accessibility and restricted
  screen/input policy with visible scope and privacy impact.
- Phase 19.10: bundle the declared open-license fonts, add a direct Console undo
  interaction, and close SSE reconnect/cancellation edge cases.
- Run the complete Phase 19 exit scenario from a freshly installed signed
  release with a live explicitly enabled VS Code extension.

## Recommended next entry point

Compose MCP ingress behind the durable task gateway and a private lifecycle
owned by `LocalProductService`. It must expose only permission-filtered Core
capabilities, use one-time local credentials, and never call a provider or
connector directly. Then add the explicit fallback configuration before
closing the Console/VS Code installed acceptance gate.
