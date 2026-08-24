# ADR 0162: Workspace edits are observe-bind-approve-verify transactions

Status: Accepted

## Context

Selecting a workspace made bounded folder and file evidence available, but a
request such as "create a plan and implement it" still stopped after discovery.
The Console also removed action capabilities from the selected application
context, and model input combined prior conversation, observations, and the
current request in one user message. Small local experts could therefore repeat
an earlier answer, emit raw observation JSON, or describe a command that never
ran.

## Decision

Current requests, earlier session memory, and authorized observations are sent
as separate inference messages. The current request is always the final user
message. Memory and observations are context-only and cannot grant authority.

The owner filesystem exposes four typed workspace capabilities:

- `os.workspace.map` performs bounded recursive, symlink-safe discovery.
- `os.workspace.retrieve` selects and reads bounded relevant UTF-8 documents.
- `os.workspace.patch` previews and changes up to four existing observed files.
- `os.workspace.patch.restore` restores exact prior bytes while the patch is
  still current.

For an implementation request, Core selects map, retrieve, and exactly one
patch action. The expert returns strict JSON plan advice and complete proposed
file contents. Core discards model-supplied authority, derives the displayed
executable plan from the exact proposed paths, binds each path to the SHA-256
digest in a real retrieval observation, and rejects unobserved paths.
The provider rechecks those digests, renders a unified diff, and waits for owner
approval. Approved writes use the scoped atomic file adapter, roll back already
written files if a later write fails, re-observe the workspace, and pass
independent SHA-256 postconditions before a verified receipt is released.

The Console sends the full capability surface of the selected context. The
Core resolver then reduces it to the least-authority capabilities required by
the current request. Capability IDs containing `patch` or `restore` classify as
application mutation so the code-capable expert and mutation output budget are
used.

## Consequences

- Model prose cannot become a command or a file mutation.
- A path named only in a prompt cannot become workspace authority.
- No file changes before the user sees and approves the exact diff.
- A stale file prevents execution instead of overwriting external work.
- Terminal text names only the plan and files recorded by the verified action
  result; it does not repeat model claims.
- The first implementation is intentionally limited to existing UTF-8 files,
  four changes, 32 KiB per proposed file, and 64 KiB total retrieved or written
  content.

## Alternatives considered

- Give the expert an unrestricted shell or PTY: rejected because model text,
  authority, execution, and evidence would collapse into one unsafe channel.
- Let the model supply expected hashes: rejected because it could invent or
  reuse authority not present in the authorized observations.
- Automatically apply a generated diff: rejected because it removes the exact
  preview and owner-confirmation boundary.
- Keep all conversation and evidence in one prompt: rejected because installed
  testing showed prior-answer repetition and raw observation leakage.

## Evidence

- `src/fam_os/core/production/generation_input.py`
- `src/fam_os/core/production/workspace_parameters.py`
- `src/fam_os/product/composition/workspace_observations.py`
- `src/fam_os/product/composition/workspace_patch.py`
- `tests/integration/test_product_os_workflows.py`
- `artifacts/product/phase19/workspace-tool-loop-20260718.json`
- `handoffs/0185-bounded-workspace-tool-loop.md`
