# Handoff 0082: Phase 9.5 verified mathematics experts

## Completed

- Added authority-free Llama 3.2 reasoning and a bounded JSON adapter.
- Added exact rational arithmetic and safe symbolic equation solvers.
- Packaged reasoning and deterministic solvers separately.
- Added strict reasoning, request, result, and evidence schemas; rendered 98 schemas.
- Ran the live two-case workstation benchmark.
- Preserved model proposals separately while deriving every pass and released result only from the deterministic solver.

## Evidence

- `artifacts/expert_fabric/phase9.5/math-expert-workstation.json`
- `tests/integration/test_math_expert_evidence.py`
- `tests/unit/test_math_experts.py`
- `tests/unit/test_sympy_math_verifier.py`
- `docs/protocols/VERIFIED_MATHEMATICS_EXPERTS.md`
- `docs/decisions/0081-model-math-reasoning-is-advisory.md`

## Next

Start Phase 9.6 with separately permissioned OCR, vision, speech-recognition, and text-to-speech packages. Do not claim live capability for a runtime or model that is not installed and observed.
