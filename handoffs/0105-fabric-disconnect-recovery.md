# Handoff 0105: Phase 12.5 recovery

Disconnect, timeout, partial-result, and verification-failure recovery discard remote output and preserve acceptance during local retry. Evidence: `tests/unit/test_fabric_scheduling_recovery.py`, ADR 0100.
