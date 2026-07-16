# Handoff 0120: Phase 14.7 reference benchmarks

**Date:** 2026-07-16  
**Plan step:** Phase 14.7  
**Status:** Complete  
**Previous handoff:** `0119-phase14-6-shell-console.md`

Minimum CPU-only and full RTX 5080 workstation evidence is now published through
one digest-bound but strictly profile-separated report. The full run records the
failed 7B attempt and verified `gemma4:26b` escalation; the constrained run
records actual admission/rejection, memory peak, and zero swap.

Validation: `.verification-venv/bin/python -m unittest tests.integration.test_reference_benchmark_publication -v`.
Next: finish the active Phase 14.4 soak, execute the product exit gate, and audit the full plan.
