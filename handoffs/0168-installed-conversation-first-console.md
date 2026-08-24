# Handoff 0168: Installed conversation-first Console

**Date:** 2026-07-18  
**Plan step:** Phase 23.3 and 23.6 readiness  
**Status:** Conversation UI installed; Phase 23 remains open  
**Previous handoff:** `0167-final-phase22-release-and-browser-retest.md`

## Objective

Replace the form-beside-debugger Weave layout with a useful conversation
surface: answers above the prompt, current-page turn history, visible machine
activity, a bounded typewriter reveal, and automatic return to the start of the
newest FAM answer after reveal.

## Design and behavior

- The primary column is now a scrollable user/FAM transcript rather than an
  input panel.
- The composer remains directly beneath the transcript and grows only to a
  bounded height. `Ctrl+Enter` or `Cmd+Enter` sends without changing normal
  multiline editing.
- Application context, exact resource, and deterministic verification live in
  a compact Task scope disclosure. Its summary always reflects the active
  selection.
- The existing plan, selected execution steps, cancellation, approval, and undo
  controls remain visible in a separate live-activity inspector.
- Each turn follows a FAM loom line instead of generic chat bubbles. User intent
  is visually distinct from the wide FAM reading surface.
- Terminal text reveals progressively for 320–1,400 milliseconds based on
  answer length. This makes completion legible without manufacturing a slow
  token stream.
- The complete answer enters a screen-reader-only polite live region
  immediately. Reduced-motion preference bypasses progressive reveal and smooth
  scrolling.
- The transcript aligns to the beginning of the newest FAM answer when reveal
  starts and again when it completes.
- Starting a new task finishes any prior reveal before appending the next turn.
  Only one Core task can be submitted at a time.
- Refresh now reloads application contexts as well as machine and integration
  state.

## Implementation

- `src/fam_os/console/static/index.html` defines the transcript, composer,
  activity inspector, and reusable turn template.
- `src/fam_os/console/static/styles.css` implements the responsive desktop and
  mobile layout, focus states, reduced motion, and FAM loom-line treatment.
- `src/fam_os/console/static/conversation.js` provides bounded reveal and
  message-start scrolling as a browser/Node-compatible small module.
- `src/fam_os/console/static/app.js` owns page-session turns, composer state,
  result rendering, accessibility text, and activity synchronization.
- `src/fam_os/console/http.py` serves the new script under the existing
  loopback-only, no-store, self-only CSP boundary.

## Validation

- 1,189 source tests passed with three declared environment-dependent skips.
- Ruff passed for source, tests, and tools.
- All 283 generated schemas validate.
- Node syntax checks pass for `app.js` and `conversation.js`.
- New deterministic Node regressions prove progressive exact completion,
  bounded duration, reduced-motion immediate output, and exact message-start
  scroll coordinates.
- The loopback HTTP integration test proves the new DOM, script binding,
  conversation asset route, session-expiry handling, citations, and prior
  monotonic task-update policy.
- Fresh signed seven-component release
  `fam-os-current-test-20260718-14` is active and healthy at
  `/home/demimagic/.local/share/fam-os-current`.
- Signed bundle manifest SHA-256:
  `7792b274a0089548f9a741f6a4957c61336d7c968b4647d2872a6f1b2b3718d8`.
- Installed `index.html`, `styles.css`, `app.js`, `conversation.js`, and
  `task_updates.js` exactly match their source SHA-256 values.
- The owner service is active on port 8765, and the VS Code connector is
  established on the new application socket.
- The ephemeral private signing key was removed after the healthy update; the
  owner installation retains only its public trust key.

## Explicit limitations

- Conversation turns are current-page UI state. FAM's task/evidence records are
  durable, but a durable user-facing conversation ledger has not been added.
- The typewriter represents release presentation, not backend token streaming.
- Phase 23 still requires installed scenario matrices, prolonged pressure and
  restart testing, security review, and fresh-user rollback/removal evidence.

## Next entry point

Use the installed Console for owner testing, then continue Phase 23.1–23.3 with
the clean profile and installed scenario matrices. Any future conversation
persistence must define retention, deletion, workspace scope, encryption, and
memory authority before storing prompt history.
