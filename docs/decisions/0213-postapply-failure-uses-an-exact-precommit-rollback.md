# ADR 0213: Post-apply failure uses an exact pre-commit rollback

Status: Accepted

## Context

The ordinary natural lifecycle applies an approved changeset before running
post-apply verification. If that verification failed, the task stopped in
`applied`: owner files contained the failed result, no local commit existed,
and the existing rollback checkpoint required a completed FAM Git delivery.
The incident could diagnose the failure but could not offer a real recovery
action or finish its rollback/report/closure branch.

## Decision

An applied but uncommitted changeset has a distinct pre-commit rollback
checkpoint. It binds the original preview and apply journal, exact changed
paths, current Git head, consequences, and approval digest. The local Git
boundary verifies that no delivery exists for this changeset, the head is
unchanged, and the staging area is empty both when presenting the checkpoint
and immediately before rollback. The candidate transaction adapter still
performs the authoritative per-path content and journal checks.

After a separate owner approval, Core persists rollback intent before restoring
only unchanged FAM-owned paths. The lifecycle records a candidate rollback
without claiming a Git action or altering history. A completed real rollback
advances the associated incident from `remediation_proposed` through typed
rollback, structured post-incident report, and closure receipts. Every step is
restart-idempotent; an already completed rollback reuses its stored decision
and receipts rather than a new confirmation or effect.

Console and Shell distinguish this required recovery choice from the optional
history-preserving rollback of a verified commit. If the owner declines, they
are told that failed applied files remain; the product does not claim they were
withheld or committed.

## Consequences

- Post-apply verification failure no longer strands changed uncommitted files
  without an exact recovery checkpoint.
- Pre-commit rollback cannot claim an inverse commit or silently stage owner
  content.
- The rollback branch of Phase 30.7 now has real source-composed
  remediation-proposal, rollback, report, closure, UI, and restart evidence.
- Phase 30.7 remains open for bounded repair/remediation followed by monitored
  recovery, signed-installed proof, and the final scenario matrix.

## Alternatives considered

- Automatically restore files without owner approval. Rejected because
  rollback is another owner-workspace mutation and the plan preserves an exact
  rollback checkpoint.
- Commit the failed changes so the existing inverse-commit path can run.
  Rejected because failed verification must never be represented as a valid
  delivery.
- Reuse task-global Git receipt presence to classify the changeset. Rejected
  because a multi-checkpoint task can contain earlier commits; delivery
  identity must be checked for the exact changeset.
- Close the incident immediately after diagnosis. Rejected because closure
  requires a real remediation, recovery, or rollback outcome plus reporting.

## Evidence

- `src/fam_os/core/engineering/local_git_delivery.py`
- `src/fam_os/product/engineering_loop_api.py`
- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/product/natural_engineering_incidents.py`
- `src/fam_os/adapters/shell/natural_engineering.py`
- `src/fam_os/console/static/natural_engineering.js`
- `tests/integration/test_natural_engineering_incident.py`
- `tests/unit/test_local_git_delivery_service.py`
- `tests/unit/test_fam_shell_natural_engineering.py`

## Superseded decisions

None. This adds the pre-commit failure branch alongside ADR 0205's
history-preserving rollback of a successfully committed result and extends the
typed incident evidence rule in ADR 0212.
