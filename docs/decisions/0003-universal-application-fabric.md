# ADR 0003: Universal Application Fabric is a primary product boundary

**Status:** Accepted  
**Date:** 2026-07-16

## Context

A resident model service, chat window, and a small set of custom connectors would not fulfill the FAM_OS product thesis. Users need local AI to create, work, play, and think through the applications already installed on their computer. Requiring every application to implement a native FAM connector would prevent broad use and reduce FAM_OS to another plugin platform.

The previous plan described semantic connectors late in the implementation sequence and placed the first FAM Console in productization. That made application weaving appear optional even though it is a defining product capability.

## Decision

FAM_OS will contain a first-class Universal Application Fabric between FAM Core and existing applications.

Application access follows a tiered integration ladder:

1. Native semantic connectors and typed application APIs.
2. Operating-system APIs and deterministic tool interfaces.
3. A generic Linux accessibility bridge.
4. Screen observation and controlled input as a restricted fallback.

All levels publish capabilities into one registry and use the same observation, action, permission, confirmation, audit, and verification contracts. Native connectors improve fidelity and efficiency but are not a prerequisite for useful integration.

FAM Shell will provide the first everyday user surface and a minimal control view. The complete production Shell and Console remain productization work, but a usable client and cross-application demonstration move before expert-library expansion.

The component previously named only `connectors` becomes `applications` to own the broader Application Fabric domain. Concrete Linux, accessibility, application, and vision mechanisms remain replaceable adapters.

## Consequences

- External applications become first-class capability providers rather than passive context attachments.
- Phase 2 must define application observation, action, permission, and result contracts.
- The Application Fabric and FAM Shell are implemented after the fake-driven Core lifecycle and before the full Expert Fabric registry.
- FAM_OS must support unmodified applications at reduced fidelity through generic bridges.
- Structured connectors remain preferred because they reduce context, improve safety, and provide stronger postconditions.
- Screen and input automation require stricter permission, confirmation, and verification policy.
- Application support will be graded rather than falsely described as universal; unsupported actions degrade safely.

## Alternatives considered

1. Chat and CLI only: rejected because intelligence would remain outside the user's actual workflows.
2. Native connector required for every application: rejected because adoption and application coverage would be too narrow.
3. Screenshot and simulated input for every application: rejected because it is expensive, fragile, and difficult to verify.
4. Unrestricted desktop agent authority: rejected because it violates user control, least privilege, and auditable action policy.

## Evidence

- The RNF thesis already identifies a Semantic State and Intent Bus and measures context saved by structured application state.
- The approved product definition is recorded in `docs/architecture/APPLICATION_WEAVING.md`.
- Existing FAM_OS rules already separate observation from action and require confirmation for external or irreversible effects.

