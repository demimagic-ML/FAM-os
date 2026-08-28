# Testing applications on Omarchy

FAM treats “the process started”, “the page or window appeared”, “the requested
behavior worked”, “the visual output is acceptable”, and “the app remained
healthy” as separate claims. An Application Test or Full OS engineering turn
receives stateful test tools alongside candidate filesystem and command tools.

## Web lifecycle

`app_start` launches or attaches to a loopback URL, waits for readiness and
starts system Chromium through Playwright. Each semantic snapshot creates
short-lived element references. Click, fill, select and keyboard actions return
the new snapshot. Console exceptions and failed/HTTP-error requests are retained
independently. Assertions create structured pass/fail receipts, while screenshot,
video and trace files live in `.fam-test-artifacts` inside the isolated
candidate and are excluded from final workspace reconciliation.

## Native lifecycle

`native_app_start` launches through UWSM, observes the new Hyprland client,
binds it to the owned PID and reads its bounded AT-SPI tree. Native actions can
only invoke actions advertised by current AT-SPI references. Assertions cover
text, roles and element presence. `grim` captures the exact window geometry for
visual evidence. Cleanup terminates only the session-owned process and writes
its receipt atomically with owner-only permissions.

Applications already exposed through FAM's Application Fabric use their native
connector or MCP capability before desktop fallback. When AT-SPI is unavailable,
Hyprland observation/capture remains useful; the existing screen/input transport
is the final bounded fallback.

## Fix and retest loop

Application evidence returns to the same compact engineering context. A failed
assertion, console exception, missing window or bad HTTP response is an
observation—not an automatic terminal result. The agent can inspect the source,
edit the candidate, restart the owned session and rerun the failed behavior.
Goal completion requires successful verification evidence after the last edit.

## Operator test

1. Select an existing browser application folder.
2. Choose the Application Test profile, or Full OS when a native launch needs
   graphical-session access.
3. Ask for concrete behaviors, for example: “start this calculator, verify 8 ×
   7 shows 56, verify division by zero is handled, check the console and capture
   the final screen.”
4. Watch the application-test field and tool receipts in the Console or widget.
5. Inspect `.fam-test-artifacts` through the Candidate view.
6. Accept application only after the declared assertions, build and health
   checks pass.

The environment-gated Python live test lives under `tests/live/omarchy/`; the
full clean-machine gate is `tools/omarchy/vm-e2e.sh`.
