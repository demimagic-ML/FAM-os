# Supervisor ownership

Owns the smallest possible deterministic privileged boundary: validate approved operations, apply resource controls, start or stop isolated services, and return structured status.

No model, prompt interpretation, routing policy, memory retrieval, or generative decision is allowed here.

Phase 1.7 defines provider-neutral service definitions, lifecycle status, resource limits, controller measurements, and the `ServiceLifecycle` and `ResourceObserver` ports. Concrete systemd and cgroup behavior remains in adapters.

Phase 3.1 adds the canonical typed capability boundary in `boundary.py`. Current authority includes owned unprivileged user-session lifecycle, declared service limits, observation, allowlisted device/filesystem grants, required immutable audit-event emission, failed-state recovery, and safe termination. Production authentication remains required before an external supervisor entrypoint exists.

Read `docs/architecture/SUPERVISOR_BOUNDARY.md` and ADR 0023 before expanding this package.

Phase 3.2 adds `OwnedServiceLifecycle` above the raw lifecycle port. Every start, stop, and status call requires injected authorization and principal/session ownership, and the registry refuses IDs outside the `fam-` namespace. Read `docs/architecture/OWNED_SERVICE_LIFECYCLE.md` and ADR 0024.

Phase 3.3 adds `ConstrainedServiceLifecycle` and requested-versus-applied evidence. A requested CPU, memory, swap, or task ceiling must match the live cgroup before the service is reported constrained; mismatch or unavailable data triggers compensating stop. Read `docs/architecture/APPLIED_RESOURCE_LIMITS.md` and ADR 0025.

Phase 3.4 adds opaque, expiring, single-use device/filesystem grants scoped to an owned service. Linux paths remain in a trusted Bubblewrap projector, which exposes only active service grants in a minimal mount namespace. Read `docs/architecture/CAPABILITY_ACCESS_GRANTS.md` and ADR 0026.

Phase 3.5 adds strict privacy-bounded audit intents, canonical request/outcome linkage, a durable JSONL SHA-256 chain, and required audited compositions for lifecycle, limits, and access. The local chain is tamper-evident, not protected against complete deletion or rollback without an external checkpoint. Read `docs/architecture/IMMUTABLE_SUPERVISOR_AUDIT.md` and ADR 0028.

Phase 3.6 adds `ServiceRecoveryController`, immutable termination reports, deterministic grant retirement, and a provider-neutral failed-state reset. Recovery ends at verified inactive/no-PID state; Core owns any later restart. Read `docs/architecture/SAFE_SERVICE_RECOVERY.md` and ADR 0029.

Phase 3.7 defines the attacker model, hardens identity/argument/option/path and
bounded-stop boundaries, forbids intelligence-layer imports, and proves the
combined live Phase 3 exit gate. Read `docs/security/SUPERVISOR_THREAT_MODEL.md`
and ADR 0030.
