# ADR 0027: Disclose bounded diagnostic repair context and verify strict conformance

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The original full-workstation quality baseline failed across seven 7B/14B attempts.
Repair prompts contained only bounded stderr, the prior candidate, and prose
guidance. They did not contain the trusted test source or later failing examples.
The initial prompt also compressed stable ordering, neighbor-only nodes, cycle
detection, and immutability into one paragraph.

A first stronger-model diagnostic then exposed a second problem: the functional
tests accepted code that used explicitly forbidden `set` and `min` operations.
Calling that result verified would have overstated requirement conformance.

## Decision

Add a bounded, immutable `RepairContext` to verified-code policy. It can disclose
up to 32,000 characters of trusted test source plus bounded explicit examples to a
repair expert. The default context remains empty; disclosure must be selected by
the benchmark or later policy owner.

Split the strong-model stable-toposort prompt into numbered invariants and include
the difficult input-order example. Preserve the prior candidate, bounded failure,
and general repair guidance.

Version the FAM-owned verifier behavior as `stable-toposort-v2`. Inject normalized
candidate source into verifier-owned tests, then enforce exactly one target
function, a 50-line maximum, no set syntax or `set`/`min`/`sorted` calls, no input
mutation, stable ordering, neighbor-only handling, and cycle rejection.

Keep a separate legacy functional fixture for parent RNF parity. Preserve every
original and diagnostic report; never rewrite the failed baseline into a pass.

Run Laguna and Gemma independently through fresh full-workstation services so both
models produce placement, latency, quality, and resource evidence.

## Consequences

- Repair experts can map tracebacks to exact later assertions and expected values.
- Functional success cannot override explicit source-level task constraints.
- Laguna demonstrates a real failed-attempt-to-passing-repair transition.
- Gemma demonstrates first-attempt success under the same strict gate.
- The runs exercise CPU, RAM, RTX VRAM, and NVMe rather than forcing a 16 GiB CPU profile.
- Disclosed-test success is diagnostic fitness evidence, not an estimate of unseen
  generalization or protection against test-specific overfitting.
- Future verifier packages must declare whether their tests may be disclosed.

## Alternatives considered

1. Accept the first Laguna functional pass: rejected because it violated explicit
   no-set/no-min requirements.
2. Put test source into every repair globally: rejected because hidden evaluators
   and adversarial verifiers may not permit disclosure.
3. Provide a full reference solution: rejected because examples and exact tests
   were sufficient and copying would make model fitness meaningless.
4. Replace the failed baseline artifact: rejected because historical evidence is
   immutable and the failure remains useful.
5. Run one combined Laguna-to-Gemma escalation: rejected because Laguna success
   would skip Gemma and leave no independent Gemma evidence.

## Evidence

- `src/fam_os/core/execution/repair_context.py`
- `src/fam_os/core/execution/prompts.py`
- `src/fam_os/verification/python/script.py`
- `tests/fixtures/verification/stable_topological_sort_tests.py`
- `configs/benchmarks/full-workstation-verified-smoke-laguna.json`
- `configs/benchmarks/full-workstation-verified-smoke-gemma4-26b.json`
- `artifacts/workstation/20260716T122504578152Z/`
