# Bubblewrap sandbox adapter ownership

Implements the verification sandbox port with an isolated Python process, Linux resource limits, a fixed environment, and bounded returned evidence. Bubblewrap is required by default; process-limit-only fallback must be enabled explicitly and reports its weaker isolation level.

This adapter does not own candidate policy, trusted tests, verdicts, repair guidance, or release decisions. The Phase 1 mechanism reduces risk but is not claimed as a hardened hostile multi-tenant security boundary.

Phase 3.4 also provides an owned-service definition projector for opaque filesystem and device grants. Trusted adapter configuration maps resource IDs to host paths; filesystem destinations are restricted below `/access` and device destinations below `/dev`. Active grants are selected by exact service and expiry before `systemd-run` starts Bubblewrap. See `docs/architecture/CAPABILITY_ACCESS_GRANTS.md`.
