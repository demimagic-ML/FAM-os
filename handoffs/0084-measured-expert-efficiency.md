# Handoff 0084: Phase 9.7 measured expert efficiency

## Completed

- Added strict measurement, raw power-sample, per-metric value, selection, and report contracts.
- Added independent quality-per-byte, quality-per-second, and quality-per-joule selection.
- Added a live three-model same-task benchmark.
- Derived artifact size/digest from Ollama, wall time from the inference interval, and joules from raw NVIDIA power samples.
- Refused synthetic energy estimates by contract.
- Added and validated the 100th public schema artifact.

## Evidence

- `artifacts/expert_fabric/phase9.7/expert-efficiency-workstation.json`
- `tests/integration/test_efficiency_report_evidence.py`
- `tests/unit/test_efficiency_reports.py`
- `docs/protocols/EXPERT_EFFICIENCY_SELECTION.md`
- `docs/decisions/0083-energy-selection-requires-meter-samples.md`

## Next

Start Phase 9.8 by turning benchmark history into conservative split, merge, and retirement proposals. Proposals must not mutate package lifecycle state without policy approval.
