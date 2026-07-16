# Mixed verified benchmark

The `fam.mixed-verified` v1 suite contains exactly one kernel-only, code,
mathematics, retrieval, and application case. Every case binds its fixture by
SHA-256 and names the acceptance policy that must produce its result. A report
must contain every case exactly once; `passed` is the conjunction of all cases.
The kernel case is rejected if it claims any model identity.

The stable-topological-sort v2 case remains a named regression. Its report also
requires exactly two independent escalation run references:
`laguna-xs.2:q4_K_M` and `gemma4:26b`. Each reference binds package artifact and
raw workstation report digests. Laguna's initial candidate failed and its one
bounded repair passed after the approved trusted test/example disclosure. Gemma
passed initially. No requirement was removed or verifier weakened.

Canonical suite and report:

- `configs/benchmarks/mixed-verified-v1.json`
- `artifacts/expert_fabric/phase9.1/mixed-verified-report.json`
- raw independent runs under `artifacts/expert_fabric/phase9.1/{laguna,gemma}/`

The deterministic cases execute SHA-256, SymPy symbolic/numerical acceptance,
exact retrieval citations, and the application action integration test. The code
case uses the package-gated full-workstation harness with CPU, RAM, GPU, storage,
token, timing, and verifier evidence.
