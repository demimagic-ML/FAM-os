# ADR 0164: Invalid workspace proposals repair before failure

Status: Accepted

## Context

The workspace loop asked an economical code expert for a strict action object,
but any JSON or binding error immediately terminated the plan with
`application.action.parameters_invalid`. The exact parser error, permitted paths,
and stronger installed experts were not used. Console could only display the
generic text "The execution plan failed safely," even when the real limitation
was that the plan required new files, commands, or too many changed files.

## Decision

Core owns a bounded parameter-resolution loop after application candidate
generation and before action preview. It permits exactly one same-selection
repair and one different-model strong escalation. Both consume the existing
plan-global repair/escalation token and time budget. Repair input contains the
exact structural error and only paths proven by authorized observations.

Workspace proposals require one to twelve nonempty plan strings and one to four
existing observed UTF-8 file changes. A model that cannot express the request
within that contract may return the distinct strict object
`{"unavailable_reason":"..."}`. Core uses only the object shape to classify the
outcome; model-written reason text is not released as trusted evidence.

Terminal failure carries a typed, non-releasable failure-reason reference. The
final-result policy maps known workspace codes to deterministic owner-safe
messages and an after-user-action retry disposition.

## Consequences

- A recoverable formatting or path mistake receives useful feedback instead of
  causing an immediate opaque failure.
- A second failure uses a different strongest-fitting local expert when one is
  schedulable, including the installed Laguna/Gemma tiers on the reference PC.
- The signed and packaged expert catalogs explicitly authorize both strong code
  models for application mutation; catalog scope tests prevent silent removal.
- Client-visible progress stays stable at one plan revision while repair changes
  inference revisions or model selection.
- No proposal, preview, approval, write, or action receipt exists unless the
  final object binds to authorized observations.
- Broad implementation plans remain outside this patch tool until separate
  typed create, delete, and command capabilities are implemented.
- Failure reason references are policy metadata, not releasable evidence.

## Alternatives considered

- Retry the same prompt unchanged: rejected because the previous live loop did
  this three times without feedback and reproduced the same failure.
- Accept loosely structured prose or paths not retrieved by Core: rejected
  because it would turn model output into authority.
- Expand the patch provider into a shell or unrestricted repository agent:
  rejected because new authority needs separate typed tools and approvals.

## Evidence

- `src/fam_os/core/production/action_candidate_retry.py`
- `src/fam_os/core/production/application_parameter_resolution.py`
- `src/fam_os/core/production/workspace_parameters.py`
- `src/fam_os/core/production/gateway.py`
- `src/fam_os/core/lifecycle/final_service.py`
- `configs/packages/runtime/model-catalog.json`
- `src/fam_os/product/resources/runtime/model-catalog.json`
- `tests/unit/test_action_candidate_retry.py`
- `tests/unit/test_workspace_parameters.py`
- `tests/integration/test_product_os_workflows.py`
- `artifacts/product/phase19/workspace-proposal-repair-20260718.json`
- `handoffs/0187-workspace-proposal-repair-and-escalation.md`
