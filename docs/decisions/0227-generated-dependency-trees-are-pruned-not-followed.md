# ADR 0227: Generated dependency trees are pruned, not followed

Status: Accepted

## Context

The candidate boundary rejected every workspace containing any symbolic or
hard link. That fail-closed rule protected source operations, but it also made
ordinary npm/Next.js repositories unusable because generated `.next` trees and
`node_modules/.bin` legitimately contain links. The observed owner repository
`B2B-DIS-Platform` failed before natural-language proposal creation even though
all links were confined to generated dependency/cache directories.

## Decision

Repository observation and owner-to-candidate cloning prune a closed set of
non-authoritative metadata, dependency, build, cache, virtual-environment, and
coverage directories before link validation or traversal. The initial set is:
`.git`, `.fam`, `.hg`, `.svn`, `.venv`, `venv`, `node_modules`, `target`,
`build`, `dist`, `__pycache__`, `.next`, `.cache`, and `coverage`.

FAM never follows, copies, inventories, proposes changes to, or applies changes
through those pruned entries. Symbolic links and multi-link regular files in
all authoritative source paths remain rejected. Candidate workspaces remain
strictly link-free; exact operation paths still pass no-link containment and
fresh preflight validation before apply.

## Consequences

- Normal generated npm/Next.js trees no longer prevent repository analysis or
  candidate creation.
- Dependency/build/cache output cannot become model context or a changeset.
- Source symlinks, hardlinks, traversal, and candidate tampering retain their
  previous fail-closed behavior.
- Verification that depends on owner-local generated dependencies must use a
  separately qualified toolchain or integration environment; those directories
  are not silently trusted or copied.

## Alternatives considered

- Permit every internal symlink: rejected because it would add link identity,
  persistence, race, and apply semantics to the candidate contract.
- Dereference dependency links: rejected because executable location and module
  resolution can change and because it would treat generated dependencies as
  owner-authored source.
- Keep rejecting the whole workspace: rejected because it blocks common
  repositories before any scoped authority decision.

## Evidence

- `src/fam_os/adapters/filesystem/candidate_io.py`
- `src/fam_os/adapters/filesystem/repository_evidence.py`
- `src/fam_os/adapters/filesystem/candidate_workspace.py`
- `tests/unit/test_engineering_preparation_orchestrator.py`
- 23 focused workspace/generation/adversarial tests pass.
- The selected real repository yields 138 observed files and a 238-entry
  candidate with zero `.next` or `node_modules` entries.
