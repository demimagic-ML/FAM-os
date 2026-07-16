# ADR 0092: Adaptation history stays local and includes failures

- Status: accepted
- Date: 2026-07-16

## Decision

Expert frequency profiles are learned only from local observations and count both verified and failed uses. Cache prediction continues to require digest-bound local sequences and bounded admission.
