# ADR 0050: Prove the Application Fabric with a real vertical user flow

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.12

## Context

Phases 5.1-5.11 built the registry, transports, integration levels, Shell,
native connector, and shared action safety. Continuing to add adapter surfaces
without a real user workflow risked preserving contracts that did not compose.
The existing Shell integration test used a scripted gateway and therefore did
not prove application weaving.

## Decision

Make the Phase 5 exit gate a measured vertical composition through the actual
FAM Shell socket and real adapters. Require three user scenarios—README summary,
one bounded test, and a previewed/approved file edit—plus an MCP-unavailable
rerun. Do not count adapter stubs toward the gate.

Add a live connector request broker to the existing authenticated transport,
explicit trailing-slash workspace-directory scopes, small workflow composition
modules, per-level measurement contracts, a canonical JSON report, and a
single bounded runner. Use a separate temporary VS Code profile and file.

## Consequences

The gate now proves the Ask/Plan/Approve/Result loop, an unmodified application,
official-SDK MCP, deterministic tools, a real native extension, explicit scoped
permission, trusted postconditions, recovery metadata, and audit linkage. It
also proves useful reduced fidelity rather than mere MCP error handling.

The acceptance package is a product composition seam, not a general natural
language planner. Its three prompts are intentionally allowlisted so it cannot
become a second Core or an unrestricted automation script. Future UI and
application work must reuse these Core and adapter boundaries.

## Alternatives rejected

- More fake gateway scenarios would validate presentation but not weaving.
- Driving the editor fixture instead of VS Code would not prove the extension's
  real semantic observation or workspace edit.
- Installing into the user's normal VS Code profile would create unnecessary
  persistent state.
- Treating a workspace URI as a string prefix without explicit directory syntax
  would blur exact-file permission and permit unsafe path forms.
- Calling the model summary verified would overstate the available evidence.
