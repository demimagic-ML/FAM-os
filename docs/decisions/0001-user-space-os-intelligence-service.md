# ADR 0001: User-space OS Intelligence Service

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The phrase “resident neural kernel” was confused with the Linux kernel. The existing prototype runs models through Ollama in user space while Linux cgroups enforce resource limits.

Putting generative inference inside Linux kernel space would expand privilege, increase crash risk, complicate model updates, lose compatibility with user-space inference libraries, and would not remove the physical memory-bandwidth or compute costs.

## Decision

FAM_OS will be implemented as an always-on operating-system intelligence service above the Linux kernel.

The privileged FAM Supervisor will be small, deterministic, auditable, and contain no generative model. All probabilistic intelligence will run in unprivileged, isolated user-space services.

Linux remains responsible for hardware, process scheduling, memory management, filesystems, networking, and device drivers. FAM_OS will consume existing interfaces such as systemd, cgroups, namespaces, pressure signals, device APIs, and permission systems through adapters.

## Consequences

- Model failures can be isolated and restarted without crashing the operating system.
- Experts can be installed and updated independently of the kernel.
- Existing inference runtimes and GPU/NPU libraries remain usable.
- FAM_OS can still become a complete Linux distribution or desktop environment later.
- Deep integration must use explicit Linux and application interfaces rather than unrestricted kernel access.

## Alternatives considered

1. Ordinary foreground application: safer but insufficiently persistent and integrated.
2. Linux kernel module or modified kernel inference: rejected for privilege, reliability, compatibility, and maintainability reasons.

## Evidence

- The RNF prototype ran a 2.5B coordinator and conditional 7B/14B experts through user-space Ollama.
- A user-systemd cgroup successfully enforced a 16 GiB memory ceiling with swap disabled.
- The verified tiered execution loop withheld incorrect candidates and released a passing candidate without kernel modifications.

