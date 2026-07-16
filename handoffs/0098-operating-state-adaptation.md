# Handoff 0098: Phase 11.4 operating-state policies

## Completed

- Added battery, charging, thermal, foreground-load, and idle state contracts.
- Added deterministic tier, prefetch, and background-adaptation policy.
- Added all four scenario proofs and two schemas; 126 schemas validate.

## Evidence

- `artifacts/adaptation/phase11.4/operating-policy.json`
- `tests/unit/test_operating_state_policy.py`
- `docs/protocols/OPERATING_STATE_ADAPTATION.md`
- `docs/decisions/0095-protect-user-and-hardware-before-adaptation.md`

## Next

Implement Phase 11.5 drift detection and rollback.
