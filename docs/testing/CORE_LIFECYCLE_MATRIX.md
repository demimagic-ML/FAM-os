# Phase 4 deterministic lifecycle matrix

The Phase 4 exit matrix runs entirely against in-memory registries and fakes. It
imports no Ollama, model router, systemd, Supervisor, desktop, or application
automation adapter.

Coverage includes trusted admission and routing through candidate-linked verified
release; application denial and permission expiry; cancellation and trusted
deadline timeout; blocking degradation; repair-budget exhaustion; cross-plan
confirmation replay; nonterminal finalization rejection; and proof that failed
candidate registry content remains withheld.

The canonical composed test is
`tests/integration/test_core_lifecycle_end_to_end.py`. Component-level adversarial
tests remain under `tests/unit/test_core_*` and boundary guards under
`tests/architecture/test_core_*`.
