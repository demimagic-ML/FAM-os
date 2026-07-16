# Phase 5 Cross-Application Acceptance

## Outcome

Phase 5.12 runs the real FAM Shell over its peer-authenticated Unix transport and
composes it with Core admission, routing, execution plans, permissions, action
safety, and live adapters. The canonical measured artifact is
`artifacts/application_fabric/phase5_acceptance.json`.

The recorded run passed the Phase 5 exit gate on 2026-07-16.

## User scenarios

The runner performs four Shell sessions:

1. **Summarize the current project README.** An unmodified Zenity window is
   observed through bounded AT-SPI without text, the official MCP SDK reads an
   allowlisted local resource, the scoped file adapter reads `README.md`, and
   `qwen3:1.7b` summarizes it through the Ollama runtime port.
2. **Run the application action contract test.** The allowlisted tool adapter
   invokes one exact Python unittest through the bounded shell-free runner. A
   zero process exit is released as verified evidence.
3. **Edit the temporary acceptance file.** A separate temporary VS Code profile
   loads the real FAM_OS extension. Core observes the active editor, prepares a
   revision-bound `Before` to `After` preview, FAM Shell displays an explicit
   approval, and Core executes only after approval. Trusted live editor
   observations verify the hash and version; the action produces two durable
   audit events and reversible metadata.
4. **Repeat README summarization with MCP unavailable.** No MCP process or
   capability is supplied. The same task succeeds through accessibility,
   deterministic file observation, and the local expert, and is explicitly
   marked reduced fidelity.

The workspace, VS Code profile, socket, audit directory, and edited buffer are
temporary. The normal VS Code profile and repository files are not modified.

## Production gaps closed by the acceptance

The vertical run found and fixed two integration defects:

- The authenticated Application transport could receive connector results but
  had no live Core-side request broker. `ConnectorRequestBroker` now owns live
  connections, waits for registration, correlates outbound observation/action
  requests, rejects timeouts and disconnects, and preserves registry cleanup.
- VS Code registered workspace roots while Core treated every resource scope as
  exact. Native workspace scopes now end in `/`; Core grants descendants only
  for those explicit directory scopes, parses file URIs, rejects dot segments,
  and keeps ordinary file scopes exact.

The run also exercised overlapping pre/postcondition IDs from the real editor.
Terminal audit projection now de-duplicates those identifiers without losing
evidence.

## Measurements

Each adapter boundary records success, wall latency, serialized context bytes,
FAM-process CPU time, current RSS, and `/proc/self/io` deltas. The report
aggregates attempts, successes, success rate, and resource totals by integration
level. Host inventory is separate so global GPU state is not misrepresented as
per-operation consumption.

The accepted reference run recorded:

| Level | Attempts | Success rate | Context bytes | Total latency |
|---|---:|---:|---:|---:|
| Accessibility | 2 | 100% | 148 | 1,065.0 ms |
| MCP | 1 | 100% | 217 | 457.6 ms |
| Deterministic OS/tool | 5 | 100% | 42,335 | 762.5 ms |
| Native semantic | 4 | 100% | 1,015 | 1,834.9 ms |

Native latency includes starting an isolated VS Code instance. The host snapshot
reported 24 logical CPUs, 67,017,834,496 bytes of RAM, a 16,303 MiB RTX 5080,
and a 2,013,991,550,976-byte workspace filesystem. Values are run-specific and
must be read from the artifact for comparisons.

## Run

The main interpreter needs both the MCP SDK and the Linux GI bindings. The
reference environment uses the existing MCP virtual environment; the runner
appends the distribution GI path only when GI is absent from that environment.

```bash
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python \
  tools/run_phase5_acceptance.py \
  --output artifacts/application_fabric/phase5_acceptance.json
```

The command exits zero only when all three full-fidelity scenarios succeed, at
least one result is verified, all four integration levels are present, and the
MCP-unavailable rerun succeeds.

## Interpretation limits

- One accepted run establishes integration correctness, not production failure
  rates. The attempt/success schema is ready for repeated soak runs.
- CPU, RSS, and I/O measurements cover the FAM runner process. VS Code, Ollama,
  and MCP child/provider costs require service/cgroup telemetry in Phase 7 for
  complete attribution.
- The README summary is intentionally released as completed, not verified. The
  test and editor edit are verified through deterministic evidence.
- The editor action verifies in-memory buffer state, not disk persistence.
