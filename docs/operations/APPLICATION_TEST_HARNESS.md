# Application Test Harness

FAM_OS application testing is a stateful agent capability, not a collection of
unrelated browser commands. One session owns the application process, localhost
URL, browser identity, current structured snapshot, diagnostics, assertions,
screenshots, trace, video, and cleanup.

## Install the optional runtime

```bash
python -m pip install -e '.[application-test]'
playwright install ffmpeg
```

FAM_OS can use an installed Google Chrome or Chromium executable. When the
Playwright package or a compatible browser is absent, application-test actions
are not exposed to the model.

## Authority

Select **Application test — localhost browser and candidate** in the Console.
The `application_test` profile permits candidate edits, workspace commands, a
project-local development server, localhost browser interaction, diagnostics,
and test artifacts. It does not imply Full OS or host-administration authority.

Development servers launched by the harness run in a Bubblewrap filesystem
boundary with the candidate as the writable root. The network namespace remains
shared so the browser can reach the selected localhost port. Session cleanup
stops only the process group created by that session.

## Tool lifecycle

`app_start` is available only when the browser runtime is installed. The other
application tools become available only after `app_start` has established a
valid session:

1. `app_start` launches or attaches, waits for readiness, opens the page, and
   persists the compiled checks and initial structured snapshot.
2. `app_snapshot` returns visible interactive elements with refs such as
   `s2e4`. Refs expire when a new snapshot is captured.
3. `app_click`, `app_fill`, `app_select`, and `app_press` act through a current
   ref and automatically return a new snapshot.
4. `app_screenshot` adds visual evidence when layout, canvas, charts, or games
   require it.
5. `app_console_errors` and `app_network_failures` return bounded diagnostics.
6. `app_assert` persists a typed assertion receipt with the action sequence,
   expected and observed values, diagnostics counts, and pass/fail state.
7. `app_stop` captures the final screenshot and Playwright trace, closes the
   browser context so video is finalized, stops the owned process, and persists
   the completed session record.

## Completion evidence

The testing objective compiler owns the check ledger. Model-proposed checks are
validated and the harness always adds zero-console-error and zero-network-failure
checks. Goal completion requires a passing `app_assert` receipt for every
compiled check; model text alone is not evidence.

A test-only task ends with `application_test_completed` and does not fabricate
an empty source changeset. A task that also edits the application continues
through the ordinary candidate preview, verification, and apply lifecycle.

Artifacts are retained under `.fam-test-artifacts/` in the isolated candidate
workspace. They remain inspectable with the candidate while the owner workspace
is unchanged.

## Tool coherence

Every inference step receives a fresh effective tool set:

```text
registered
∩ permitted by the selected authority
∩ available in the runtime and session
∩ relevant to the current agent phase
```

If a model emits a stale, hidden, or invented tool identifier, FAM_OS records a
`tool_registry_invariant` recovery event and returns the exact current tool list.
The call is never dispatched as an ordinary application failure.
