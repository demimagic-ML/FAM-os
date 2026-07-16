# FAM Supervisor threat model

## Scope and security claim

The Supervisor is a deterministic user-session enforcement boundary. It starts,
constrains, observes, grants access to, audits, recovers, and terminates only
declared FAM-owned services. It is not a kernel, root daemon, general process
manager, model runtime, or application automation engine.

The Phase 3 claim assumes an authenticated local caller has already been mapped
to a `SupervisorCallContext` and explicit capabilities by trusted composition.
The external authentication transport is not implemented and is therefore not
claimed by this threat model.

## Assets

- integrity of service ownership and definitions;
- CPU, RAM, swap, task, filesystem, and device isolation;
- authority and expiry of access grants;
- availability and integrity evidence of required audit records;
- reliable failed-state cleanup and termination;
- privacy of host paths, user content, prompts, model output, and raw exceptions;
- separation between deterministic Supervisor code and intelligence layers.

## Trust zones

```text
untrusted transport data
  -> authenticated context/capability authority       trusted policy boundary
  -> Supervisor contracts and use cases               deterministic boundary
  -> systemd/cgroup/Bubblewrap/audit adapters          trusted mechanism boundary
  -> owned unprivileged service                        untrusted workload
  -> Linux user session and kernel                     host boundary
```

Trusted inputs are the authorizer implementation, allowlist configuration,
adapter executable paths, installed AppArmor policy, and service definition
selected by authenticated Core policy. Model-generated text is never trusted
Supervisor intent.

## Attacker profiles

- a caller sending malformed identities, unit names, commands, limits, or grants;
- a different principal/session trying to control another caller's service;
- an authorized but compromised workload trying to escape its namespace or
  retain resources after termination;
- a same-user process trying to replace or tamper with the audit ledger;
- a provider returning missing, mismatched, stale, or malformed evidence;
- accidental intelligence-layer coupling that expands Supervisor authority.

Host root and a fully compromised user account remain outside the Phase 3
protection claim. They can inspect or modify user-owned processes and files.

## Threats and controls

| Threat | Primary controls | Executable evidence |
|---|---|---|
| Identity/control-character injection | bounded identity regexes; strict service IDs; no free-form audit fields | security transport and grant tests |
| Command option injection | shell-free argument vectors; explicit `--` before commands in systemd and Bubblewrap | option-terminator tests and live Bubblewrap smoke |
| Argument/environment exhaustion | bounded argument count/length and environment count/value length | definition exhaustion tests |
| Arbitrary system-service control | mandatory `fam-` ownership namespace; user-scoped commands; no system mode | ownership and user-scope tests |
| Cross-principal control | injected capability checks plus principal/session ownership before adapters | lifecycle, access, recovery denial tests |
| Limit bypass or false success | requested-versus-applied cgroup verification; unknown/unavailable evidence fails closed | constrained unit and live tests |
| Filesystem/device escape | opaque grants; trusted mapping; `/access` and `/dev` destinations; minimal Bubblewrap namespace; no home by default | access unit and live tests |
| Stale access after termination | stop/no-PID verification followed by stable revocation of every unrevoked service grant | recovery unit tests |
| Workload ignores termination | explicit systemd control-group kill, SIGKILL fallback, bounded stop grace | live Bubblewrap termination proof |
| Audit insertion/modification/truncation | canonical strict records; sequence/digest chain; duplicate IDs; locked append; fsync | audit integrity tests |
| Audit path replacement | no-follow file open; regular/current-owner/0600 file; secure nonsymlink parent | audit path security tests |
| Recovery ambiguity | failed-only recovery; provider-neutral reset-failed; inactive/no-PID requirement; `UNKNOWN` rejected | recovery unit and live tests |
| Intelligence-boundary creep | explicit non-goals and architecture test forbidding Core/routing/expert/memory/application imports | security import test |

## Fail-closed behavior

- authorization, ownership, unknown resource, expired scope, and evidence mismatch
  are rejected before success;
- a missing required request audit record prevents the effect;
- a new service or grant is compensated when its success outcome cannot be
  recorded;
- resource-limit mismatch stops the service;
- unknown recovery state and noninactive terminal evidence are failures;
- an invalid audit chain blocks later append;
- a failed safe-termination cleanup returns no successful report.

## Residual risks and required future controls

- The authenticated local transport and credential binding remain unimplemented.
- Ownership and grant registries are in-memory and not crash-durable.
- A same-user attacker can delete or roll back the complete local audit ledger;
  Phase 14 needs a trusted external head or write-once/remote journal.
- Trusted resource mappings can still be misconfigured, and host path replacement
  between configuration and bind is not protected by an FD-based mount API.
- A compromised authorized Core can select an unsafe user-level executable. The
  Supervisor constrains execution but does not independently understand command
  semantics; production package manifests and install policy must bind approved
  definitions to digests.
- The dedicated FAM AppArmor profile is not packaged yet. Live tests use an
  already installed local profile where the host requires it.
- Advisory audit locks do not constrain writers that deliberately ignore them.
- Denial of service within declared limits, disk exhaustion, thermal stress,
  long-running crash loops, and multi-user isolation require later phase tests.

These residuals are explicit exclusions, not reasons to weaken current checks.

## Phase 3 exit evidence

The combined opt-in smoke starts one unprivileged FAM user service, applies and
verifies CPU/RAM/swap/task ceilings, reads its live cgroup snapshot, writes the
required audit sequence, safely terminates it, proves inactive/no-PID state, and
verifies the complete private ledger. Separate live tests prove allowlist-only
filesystem/device projection and failed-state reset.
