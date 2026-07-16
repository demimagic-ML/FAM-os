# Restricted Screen Observation and Input Fallback

## Purpose

Phase 5.10 supplies the last level of the Application Fabric integration ladder.
It exists for custom canvases or inaccessible application surfaces that cannot
be represented by a native connector, deterministic OS/tool API, or AT-SPI. It
is never the default application representation and its availability does not
grant permission to observe or act.

The provider-neutral contracts live in `fam_os.applications.screen_input`. X11,
Pillow, and XTest remain optional Linux adapter details.

## Exact target scope

Every operation identifies one application ID, process ID, and opaque window ID.
The reference X11 provider requires that exact window to be viewable, owned by
the exact process, and currently focused. Capture is restricted to the focused
window rectangle; full-desktop capture and background-window input are absent.

Window inspection uses only bounded, shell-free `xprop` and `xwininfo` calls with
absolute executables, a one-second timeout, bounded output, and a minimal
environment. Titles are not requested. A Wayland or headless session returns
explicit unavailability because the X11 implementation must not pretend to have
portal or compositor authority it does not possess.

The X11 rectangle can include an overlapping system surface or another
always-on-top window. This is an inherent limitation of screen pixels and is one
reason semantic and accessibility levels remain preferred.

## Capture bounds and privacy

The bridge separates capture availability from input availability. A missing
XTest backend does not disable an otherwise authorized observation.

Default bounds are:

- at most 16,000,000 source-window pixels before any allocation;
- at most 2,000,000 encoded pixels after deterministic downscaling;
- at most 4 MiB of PNG data; and
- exactly `image/png`, with a verified SHA-256 over the encoded bytes.

Pillow is imported only by the optional capture provider. The provider rejects
an oversized source before `ImageGrab`, downscales before encoding, and fails
closed if the PNG remains over its byte budget. FAM does not OCR, log, or persist
the bytes in this adapter. The caller still needs explicit observation authority
and must apply its own context-retention policy.

An observation's scene ID binds the window ID, source dimensions, and exact PNG
digest. Pixels are untrusted application evidence, not instructions.

## Controlled input surface

The initial input surface contains only:

- one left pointer click at integer millionth-relative window coordinates; or
- one chord of at most four keys from a small exact allowlist.

The default key allowlist contains navigation keys, Return, Escape, Tab,
Backspace, left Control, left Shift, and `z`. There is no arbitrary text entry,
clipboard access, drag, double-click, scrolling, generic key code, shell,
application command, file operation, or window-management surface.

The Application Fabric declaration marks input irreversible and
always-confirmed. The adapter cannot perform confirmation itself.

## Stale-scene lifecycle

Input uses a two-stage lifecycle:

1. Core supplies an exact scene ID and one bounded instruction.
2. Preparation validates the allowlist, confirms the input backend exists,
   recaptures the target, and rejects any scene change.
3. Core applies permission, proposal, and explicit confirmation policy.
4. Execution verifies the instruction digest, recaptures the complete scene,
   rejects any post-approval change, and rechecks exact focus, process, window,
   and geometry immediately inside the provider.
5. The provider emits one input primitive and the bridge attempts a bounded
   post-action capture.

The returned evidence contains invocation status and before/after scene IDs. It
does not claim that the intended user outcome happened. Immediate pixels may be
unchanged, an application can ignore input, and the target can change after the
last recheck. Core must compose a task-specific postcondition and must never
release success from the provider's boolean alone.

## Concrete provider boundary

- `X11WindowInspector` resolves exact focus, process identity, viewability, and
  geometry through the existing bounded command runner.
- `PillowPngCapture` owns the optional pixel capture and PNG encoding.
- `XTestInput` owns the minimal `libX11`/`libXtst` calls. It exposes no generic
  library handle and opens/closes the display per input operation.
- `X11ScreenInputProvider` rechecks target identity at both capture and input
  boundaries and maps relative coordinates only after that recheck.
- `ScreenInputBridge` owns policy, exact-scene preparation, evidence, and safe
  unavailability without importing any provider SDK.

No module imports Core, models, experts, routing, verification, Supervisor, or
MCP. No screen/input module directly spawns a process.

## Live evidence

The live test discovers the current focused X11 window without titles, confirms
its process/window/geometry identity through the bounded inspector, and probes
whether the optional capture and XTest backends are available. It deliberately
captures no pixels and sends no input. Real screen content and mutation require
an explicitly authorized product flow, not an automatic test.
