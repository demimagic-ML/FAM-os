# Adaptive local coding-agent harness

FAM_OS runs coding work as a durable execution graph rather than a single chat
completion. Each model step passes through `prepare`, `infer`, `execute`,
`observe`, `recover`, `verify`, and a terminal node. SQLite checkpoints are
written at every action boundary. If the process stops while a turn is running,
the same turn identity restores completed tool calls and continues from the next
step instead of replaying mutations.

The thread goal ledger retains the original request, accepted plan, current
objective, completed objectives, and unresolved work. The context compiler
constructs every inference request from that typed state and bounded recent
evidence. It compacts incrementally and can restart with a clean context while
preserving the goal, changed-file evidence, latest observations, and errors.

Tool exposure is phase-aware. A large registry initially exposes the smallest
useful discovery set, including basic file and directory creation. The model can
call `request_capabilities` to expose the remaining tools on its next step; a
rejected premature completion also expands the set automatically. Filesystem mutations return machine-checked
semantic postconditions. Command failures are real failed tool results and enter
the typed recovery router; a nonzero exit is never represented as success. A
missing executable includes bounded, real sandbox-visible alternatives instead
of asking the model to guess or repeatedly invoke package installers.

Completion and verification are separate graph nodes. The model may propose a
final response, but verification relies only on semantic postconditions and
successful verification commands.
After a successful `verify_command`, the graph enters a tool-free finalization
phase so the model returns the result instead of continuing to explore.

## Reproducible model evaluation

Run the same eight stateful cases against each installed model:

```bash
PYTHONPATH=src .verification-venv/bin/python tools/run_agent_harness_eval.py \
  --model devstral-small-2:latest \
  --endpoint http://127.0.0.1:11434 \
  --scorecard ~/.local/share/fam-os/agent-model-scorecard.json
```

The suite covers file reading, a directory outside Git, multi-file edits,
accepted-plan continuation, missing-command recovery, approval resume, a failing
test repair, and twenty-tool goal retention. Model routing reads the versioned
scorecard and ranks models by measured completion rate, then pass count and
latency. Static preferences are used only when no complete eight-case result is
available.

Qwen3.8 uses Ollama's native `thinking` field. FAM_OS requests phase-scaled
reasoning effort, preserves useful reasoning only in the provider-native
assistant/tool exchange, and excludes it from ordinary conversation history.
