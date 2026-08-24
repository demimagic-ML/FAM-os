# ADR 0161: Workspaces grant resource authority and terminals show evidence

Status: Accepted

## Context

FAM Console could attach a connected application context but could not select
an ordinary local folder. The owner filesystem provider could inspect whether
a directory existed but could not list it or read a selected file. A model
therefore sometimes printed an `ls` command in prose even though no command was
executed, making FAM_OS look like a chatbot pretending to use a terminal.

## Decision

Console provides an authenticated, owner-local folder browser rooted at the
owner's home directory. Choosing a folder or file adds its exact `file:` URI to
the task permission scope. Core can acquire bounded, descriptor-relative
directory listings and bounded, no-follow file observations through typed
Application Fabric capabilities.

The left-side Tool terminal is an evidence ledger, not a general shell. It
renders only Core application observations, proposals, action results, and
receipt identifiers. Model text is never interpreted as a command. Process
execution remains limited to configured fixed tools and continues to require
Core admission, confirmation when applicable, postconditions, and audit.

Exact folder-list questions are rendered directly from the observation record
without model inference. Requests that require explanation or analysis may use
an expert, but the observations and machine-action receipts remain separately
visible.

## Consequences

- Users can see and select the folder in which FAM may work.
- Directory and file evidence has explicit resource authority and bounded size.
- Simple listings cannot acquire model spelling or omission errors.
- The terminal cannot become an unreviewed arbitrary-shell escape hatch.
- Whole-repository autonomous analysis still requires a bounded multi-step tool
  planner; this decision establishes its permission and evidence boundary.

## Alternatives considered

- Give the model a raw PTY: rejected because it collapses model output,
  execution authority, approval, and evidence into one unsafe channel.
- Treat any path typed in a prompt as authority: rejected because mentioning a
  path is not an explicit permission grant.
- Continue synthesizing exact file lists with a model: rejected after installed
  testing demonstrated a filename rewrite despite correct observations.

## Evidence

- `src/fam_os/console/workspaces.py`
- `src/fam_os/console/task_activity.py`
- `src/fam_os/core/production/deterministic_observation.py`
- `src/fam_os/product/composition/owner_filesystem.py`
- `artifacts/product/phase19/workspace-tools-20260718.json`
- `handoffs/0184-owner-workspaces-and-tool-evidence-terminal.md`

