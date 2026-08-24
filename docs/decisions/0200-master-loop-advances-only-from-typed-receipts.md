# ADR 0200: Master loop advances only from typed receipts

Status: Accepted

## Context

The master loop stores compact evidence identifiers, but an identifier supplied
by a caller does not prove that inspection, verification, mutation, Git, or
publication occurred. Installed controls therefore need a trusted translation
boundary between concrete service outputs and lifecycle state.

## Decision

`EngineeringLifecycleDriver` is the only product-composed path for forward
stage advancement. It accepts concrete typed `RepositoryAnalysis`,
`ArchitectureProposal`, `CandidateWorkspace`, `EngineeringEvidence`,
`CandidateTransactionPreview`, `CheckpointDecision`, `CandidateApplyReceipt`,
`GitLocalActionReceipt`, `GitPublicationApproval`, and
`GitPublicationReceipt` objects.

The driver checks task, candidate, analysis, checkpoint, action, approval,
status, and receipt identities before advancing. Successful verification is
required. Apply requires an approved exact pending checkpoint. Publication
requires the exact pending single-use approval. Rollback requires a complete
rollback receipt. Every operation revalidates the active, reconfirmed,
unexpired, exact task grant through an injected Core policy.

Console and Shell continue to expose no generic evidence-ID advancement.

## Consequences

- Claimed strings cannot move a production-composed task forward.
- Grant revocation or expiry blocks the next receipt transition.
- Typed services can be wired incrementally without weakening loop policy.
- The remaining Phase 30.1/30.9 gap is active orchestration that invokes all
  component services, not the receipt-to-state trust boundary.

## Evidence

- `src/fam_os/core/engineering/lifecycle_driver.py`
- `src/fam_os/product/engineering_loop_api.py`
- `tests/unit/test_engineering_lifecycle_driver.py`
- `tests/unit/test_product_engineering_loop_api.py`

## Superseded decisions

None. This completes the trusted transition boundary introduced by ADR 0198.
