# ADR 0231: Natural engineering plan references are session and workspace bound

Status: Accepted

## Context

The Console sent every natural-engineering prompt as an independent task. A
follow-up such as `Implement the plan` therefore had no access to the plan from
the preceding repository-analysis task. The repository planner scored only the
words in that short follow-up, so an unrelated file could become the candidate
target. Sending all previous conversation as authority-bearing intent would
instead let stale or untrusted text widen the owner's grant.

## Decision

FAM Core keeps a bounded reference to the latest owner-approved analysis plan
for each exact `(owner, authenticated transport session, canonical workspace)`
tuple. A plan reference is recorded only after the read-only engineering grant
is approved and repository preparation produces a complete architecture
proposal.

Explicit follow-up language such as `Implement the plan` may resolve that plan
into the task intent used by repository planning and candidate generation. The
current user message remains the only input to authority inference, high-risk
classification, and the grant's originating intent. Referenced plan text is
labelled context-only and cannot grant publish, network, secret, raw-shell,
host-administration, or production authority.

If no plan exists in the same session and workspace, FAM rejects the reference
before creating a grant and asks for a plan or a self-contained request. The
Console displays the repository-grounded plan and tells the owner that it is
available for a same-session follow-up.

## Consequences

- Browser and Shell follow-ups can implement the plan they just approved.
- A plan from another browser session, owner, or workspace cannot be reused.
- Approval boundaries are unchanged; plan context cannot add authority.
- The reference cache is intentionally process-local and bounded. Durable task
  and plan artifacts remain in engineering storage, but automatic reference
  recovery after a service restart is future work.

## Alternatives considered

- Treat every prompt as independent: rejected because ordinary conversational
  follow-ups lose the repository plan and can select irrelevant paths.
- Concatenate unrestricted conversation history before authority admission:
  rejected because stale context could change granted powers.
- Let the model infer which prior task was intended: rejected because the
  owner/session/workspace binding must be deterministic.

## Evidence

- `src/fam_os/core/engineering/natural_conversation.py`
- `src/fam_os/core/engineering/natural_language.py`
- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/console/natural_engineering_routes.py`
- `src/fam_os/console/static/natural_engineering.js`
- `tests/unit/test_natural_engineering_conversation.py`
- `tests/unit/test_product_natural_engineering_api.py`
- `artifacts/product/phase30/natural-plan-followup-acceptance-20260719-01/evidence.json`
