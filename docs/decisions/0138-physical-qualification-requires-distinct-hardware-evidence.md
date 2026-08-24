# ADR 0138: Physical qualification requires distinct hardware evidence

**Status:** Accepted  
**Date:** 2026-07-17  
**Extends:** ADR 0137

## Context

Two installation prefixes, network namespaces, containers, virtual machines,
or simulated peers can exercise the trusted-fabric protocol without proving
that it survives real host, network, storage, and service boundaries. Recording
raw machine identifiers or network addresses would create unnecessary durable
device data.

## Decision

Phase 21.7 requires the same signed release installed on two distinct physical
Linux machines. Installed code emits strict content-free
`PhysicalHostEvidence` containing hashes of machine identity, physical hardware
anchor, hostname, CPU, block devices, and non-loopback network state together
with release, component, installation-health, kernel, architecture, RAM, and
virtualization facts.

The probe fails closed for virtualized or unknown environments, absent hardware
anchors, loopback-only networking, unhealthy installations, or an incomplete
signed component set. The final report validator requires distinct machine and
hardware-anchor hashes, the same signed seven-component release, the expected
requester and expert-peer roles, real remote-success evidence, peer-loss local
recovery under unchanged acceptance, content-free storage observations, healthy
diagnosis, and complete removal on both hosts.

The physical anchor is an accessible DMI product UUID, device-tree serial, or
non-virtual block-device hardware serial. The probe remains unprivileged and
tries the next supported source when firmware permissions hide an earlier one;
it never substitutes hostname, machine ID, or a generated value for hardware.

No localhost or same-host result may mark Phase 21.7 complete, even if every
protocol assertion passes. The Master Plan remains in progress until the
cross-host report is captured and validated.

## Consequences

- Physical qualification has an explicit machine boundary instead of relying
  on operator narrative.
- Durable reports avoid raw host identifiers and network addresses.
- A second physical Linux host is a real exit-gate dependency, not something a
  simulation can waive.
- The qualification probe and validator can be prepared and source-tested
  before the second host is available without overstating completion.
