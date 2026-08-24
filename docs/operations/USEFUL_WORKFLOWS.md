# Useful workflows

FAM_OS exposes useful work at `http://127.0.0.1:8765/` after the local launcher
exchanges the Console bootstrap token. The **Workflows** screen is deliberately
artifact-first: a successful run writes into
`<workspace>/.fam-output/<task-id>/` and retains the task, artifact digests, and
bounded execution timeline in the private product database.

## Built-in workflow families

| Workflow ID | Inputs | Produced artifacts |
|---|---|---|
| `documents.summarize-pdf` | PDFs inside the selected workspace | `summary.md` |
| `data.analyze-csv` | One CSV | `analysis.md`, `chart.svg` |
| `media.transcribe-audio` | WAV, MP3, M4A, OGG, or FLAC | `transcript.md` |
| `research.cited-brief` | One to ten HTTP(S) source URLs | `research.md` |
| `engineering.issue-to-change` | Repository workspace and instructions | governed engineering proposal plus handoff artifact |

Input paths must resolve inside the selected workspace. If no paths are given,
FAM discovers matching files recursively while excluding prior `.fam-output`
directories.

## Durable work

`GET /api/v1/useful/tasks` lists recent work. The query parameters `q`,
`project_id`, `attention`, `limit`, and `offset` support the Console history and
inbox. A task can be inspected, retried, or forked:

```text
GET  /api/v1/useful/tasks/<task-id>
GET  /api/v1/useful/tasks/<task-id>/timeline
POST /api/v1/useful/tasks/<task-id>/retry
POST /api/v1/useful/tasks/<task-id>/fork
GET  /api/v1/useful/artifacts/<artifact-id>
```

Retry preserves the complete original request. Fork accepts only bounded input
overrides and retains the parent task ID.

## Integration Center

The Applications screen lists the initial qualified connector catalog:
filesystem, Git, web fetch, time, browser, calendar, email, and PostgreSQL.
Configuration and readiness state are stored locally. A missing executable is
reported as `missing_runtime`; it is never presented as connected.

## Automations

Automations bind one saved workflow request to a `manual`, `interval`,
`webhook`, or `file_changed` trigger. Run modes are `single`, `restart`,
`queued`, and `parallel`. Every execution creates a durable automation-run row,
a normal useful task with its own tool timeline, and an owner-visible
notification.

## Recipes

The recipe library contains ten built-in recipes covering document summaries,
CSV reporting, audio transcription, research, and repository engineering.
Owners can also persist custom request templates and execute them with only the
workspace-specific inputs supplied at run time.
