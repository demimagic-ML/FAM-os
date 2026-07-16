# Scheduler Configuration Layering

This package owns deterministic composition of:

1. complete safe defaults;
2. read-only discovered inventory and enforcement ceilings;
3. one trusted named validation profile;
4. an optional user restriction;
5. an optional active session restriction.

Trusted profiles may replace default operating values but remain clamped by discovery and enforcement. User and session layers are monotonic restrictions: maximums can only decrease, reserves can only increase, and accelerator permission is combined with logical AND.

The output is an `EffectiveResourceBudget` plus structured decisions. This package does not discover hardware, mutate cgroups, select experts, or execute providers.

`profiles.py` joins a named scheduler configuration to a provider-neutral service envelope. The concrete checked documents live in `configs/profiles/`; live machine state is deliberately separate. See `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md` and ADR 0020.
