# ADR 0048: Restrict screen and input fallback to exact active-window scenes

**Status:** Accepted  
**Date:** 2026-07-16  
**Plan step:** Phase 5.10

## Context

FAM_OS must remain useful when an application exposes neither a semantic
connector, a deterministic tool/API, nor sufficient accessibility semantics.
Pixels and simulated input can cover those gaps, but unrestricted desktop
capture or input would be privacy-invasive, fragile, hard to verify, and far
more powerful than the requested application scope.

## Decision

Implement a provider-neutral level-4 adapter with these constraints:

- target one exact application ID, process ID, and active window ID;
- expose separate observation and input availability/authority;
- capture only the active window rectangle with strict source-pixel,
  encoded-pixel, PNG-byte, and media-type bounds;
- bind proposals to an exact scene digest and recheck the full scene after
  confirmation;
- expose only one left click or one small allowlisted key chord;
- recheck focus, process, window, and geometry inside the input provider;
- declare every input irreversible and always-confirmed;
- report invocation and before/after frames as evidence, never as proof of the
  task's outcome; and
- degrade explicitly outside the implemented X11 provider instead of using an
  unreviewed compositor, portal, or device-injection workaround.

Use bounded shell-free X11 metadata tools, optional Pillow capture, and a narrow
XTest binding behind separate ports. Do not expose text entry, clipboard, drag,
scroll, arbitrary key codes, generic commands, full-desktop capture, or
background-window input in the initial surface.

## Consequences

Unmodified custom-canvas applications have a real but intentionally narrow
fallback. Exact scene matching favors safety over liveness and can reject pages
with animation, blinking cursors, video, or transient overlays. X11 rectangular
capture may include an overlapping surface. These limitations must cause
degradation or user-guided execution, not relaxed matching.

Pillow and XTest can be independently unavailable. The adapter's evidence
cannot establish task success; Phase 5.11 and task-specific verifiers must bind
stronger preconditions, postconditions, audit, and compensation where possible.

## Alternatives rejected

- Full-desktop screenshots expose unrelated applications and notifications.
- Approximate image matching creates ambiguous authority around changed scenes.
- Arbitrary typing or key codes silently create a general desktop-control API.
- Background-window input weakens the user's ability to see the active target.
- Treating successful injection as successful intent violates verification
  policy.
- Claiming Wayland support through X11 compatibility would hide unavailable
  compositor/portal authorization semantics.
