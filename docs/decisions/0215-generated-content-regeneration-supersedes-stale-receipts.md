# ADR 0215: Generated-content regeneration supersedes stale receipts

Status: Accepted

## Context

Release-signed documentation generation could create governed output and block
an apply when its source or output became stale. It could not recover inside a
repair: the old receipt remained the only gate, ownership/regeneration files
were checked for existence but not bound by digest, and the natural path did
not persist its policy conclusion or create requirement traces. A source repair
therefore either stopped before remediation or would have risked approving
documentation for an intermediate candidate.

## Decision

Every documentation policy evaluation creates an immutable
`DocumentationRequirementSelection` binding the task, candidate, policy ID,
intent digest, exact required kinds, and evaluation time. Product admission
recomputes the policy result from the durable owner task; a caller cannot claim
that a required kind was absent. An empty required-kind set is a stored
conclusion rather than missing work.

Each admitted generation receipt now has a Core-derived
`DocumentationGovernanceBinding`. Core re-hashes the ownership,
authoritative-regeneration, and task-requirement anchor files in the candidate
and binds their paths and digests to the exact request. The requirement anchor
contains the task and acceptance digests but not the raw prompt, credential, or
private user data.

When a repair changes source files, the natural documentation coordinator
derives a new request identity from current source and governance digests,
reruns only the installed release-signed byte producer, writes the new output
through ordinary candidate edits, admits a new binding and receipt, and then
runs signed candidate verification over the final code plus regenerated
content. The old receipt and its stale report remain immutable evidence. Apply
groups receipts by output and requires at least one receipt whose sources,
governance files, and output all match the current candidate. A newer current
receipt therefore supersedes an older stale receipt without deleting history.

After final passing verification, Core deterministically records one
`RequirementTraceabilityRecord` from the non-generated changed implementation
paths, affected or changed test paths, and actual passing verifier evidence. It
uses the generated task-requirement anchor as the repository source. A trace is
`satisfied` only when implementation, test, and trusted evidence are all
present; otherwise it is explicitly `partial`. Trace identity and timestamp
are replay-stable.

## Consequences

- Documentation-bearing natural tasks may use the same bounded repair path as
  ordinary code tasks without approving stale output.
- Ownership, regeneration instructions, and the requirement anchor are
  content-bound, not existence-only controls.
- Historical stale generations remain inspectable while the exact current
  generation alone permits apply.
- “Not required” is distinguishable from a missing generator run.
- Natural generated-content tasks receive an automatic truthful
  requirement-to-code-test-evidence trace.
- Existing pre-ADR receipts without a governance binding fail closed if a
  pending task attempts apply after upgrade; their generation-time governance
  state cannot be reconstructed honestly.
- Phase 30.6 is source-composed but remains open for a new signed installation,
  live production-verifier proof, and final scenario qualification.

## Alternatives considered

- Delete or rewrite the old receipt after regeneration. Rejected because
  governance evidence is append-only and failures must remain observable.
- Treat any stale historical receipt as permanently blocking. Rejected because
  it makes correct authoritative regeneration impossible.
- Pick the newest timestamp without re-hashing candidate state. Rejected
  because time is not evidence that output is current.
- Store the raw user prompt in the repository requirement anchor. Rejected to
  prevent credential or private-data disclosure into candidate and Git state.
- Mark every generated trace satisfied. Rejected because missing test paths or
  verifier evidence must reduce assurance truthfully.

## Evidence

- `src/fam_os/core/engineering/documentation.py`
- `src/fam_os/core/engineering/documentation_service.py`
- `src/fam_os/product/engineering_documentation_api.py`
- `src/fam_os/product/natural_engineering_documentation.py`
- `src/fam_os/product/natural_engineering_trace.py`
- `src/fam_os/product/natural_engineering_repair.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `tests/integration/test_natural_engineering_incident.py`
- `tests/unit/test_product_engineering_documentation_api.py`
- `tests/unit/test_documentation_recipes.py`

## Superseded decisions

None. This completes the source regeneration and trace continuation anticipated
by ADRs 0210 and 0211 and extends ADR 0214's repair branch.
