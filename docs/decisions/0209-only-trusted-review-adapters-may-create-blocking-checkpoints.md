# ADR 0209: Only trusted review adapters may create blocking checkpoints

Status: Accepted

## Context

ADR 0199 defined independent review contracts, but they were not attached to
the active candidate changeset. Exposing a transport that accepts arbitrary
review documents or claimed resolution identifiers would let a model or caller
self-attest a pass and would violate the receipt-driven lifecycle boundary.

## Decision

The product engineering loop accepts a review checkpoint only through an
internal trusted-review attachment interface. Core verifies the checkpoint's
task, candidate, and complete changeset-preview digest against its own persisted
records. The producer and reviewer must remain distinct under the existing
contract.

Every attached checkpoint for the exact changeset is a passage gate. Any open
finding blocks apply. Console and Shell expose review state as read-only task
data; they do not accept checkpoint creation or a caller-claimed resolution
receipt. A later signed reviewer or receipt resolver must call the internal
service after validating its own evidence.

Review documents are owner-bound AEAD records in installed composition. Only
task identity and optimistic revision metadata remain indexable outside the
ciphertext. The former strict plaintext component format is migrated only when
unambiguously recognized.

## Consequences

- A recorded finding cannot be ignored by the ordinary changeset apply path.
- Review state survives restart and is visible from both owner clients.
- Models and transports cannot manufacture a review pass or remediation
  receipt.
- Existing tasks without a policy-selected checkpoint continue normally.
- Phase 30.8 remains open until a production policy selector and independent
  signed/human reviewer adapter create the required checkpoints and typed
  remediation receipts in the installed product.

## Alternatives considered

- Let Console or Shell submit review JSON. Rejected because caller-supplied
  status is not trusted review evidence.
- Treat review findings as advisory display fields. Rejected because selected
  review checkpoints are required to block.
- Require a review for every task immediately. Rejected until the independent
  reviewer and selection policy are production-composed; doing so would make
  the ordinary lifecycle unavailable without adding assurance.

## Evidence

- `src/fam_os/product/engineering_review_api.py`
- `src/fam_os/product/engineering_loop_api.py`
- `src/fam_os/adapters/sqlite/engineering_review.py`
- `src/fam_os/console/engineering_loop_routes.py`
- `src/fam_os/shell/engineering_loop_contracts.py`
- `tests/unit/test_product_engineering_review_api.py`
- `tests/unit/test_engineering_review_service.py`
- `tests/integration/test_console_engineering_loop.py`
- `tests/unit/test_fam_shell_engineering_loop_transport.py`

## Superseded decisions

None. This operationalizes the passage consequences of ADR 0199.
