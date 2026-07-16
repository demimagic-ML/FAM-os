# Handoff 0011: Full hardware and MCP plan

**Date:** 2026-07-16  
**Plan step:** Phase 2.2, Phase 5.2-5.4, and Phase 7.6 planning  
**Status:** Complete  
**Previous handoff:** `0010-parent-prototype-read-only.md`

## Objective

Ensure the post-Phase-1 plan uses the reference test PC's full CPU, RAM, RTX VRAM, and NVMe capabilities without losing the 16 GiB CPU-only compatibility baseline, and make MCP's exact role in application weaving understandable and architecturally bounded before Phase 2 contracts are implemented.

## Scope completed

- Verified the current Linux workstation through read-only GPU, CPU, memory, block-device, filesystem, and Ollama probes.
- Defined `compat-cpu-16gb` as the required minimum-machine regression profile.
- Defined `full-reference-workstation` as the quality-first profile with GPU visibility, all CPUs visible, no artificial 16 GiB ceiling, explicit OS headroom, and measured NVMe use.
- Required verified quality comparison before throughput or memory optimization claims.
- Required separate CPU, RAM, VRAM, transfer, SSD I/O, cgroup pressure, swap, and OOM telemetry.
- Clarified that SSD is storage/cache/memory-map backing rather than added RAM.
- Defined MCP as a replaceable Application Fabric connector protocol rather than FAM_OS's internal capability or permission model.
- Defined FAM_OS as both an MCP client/host for approved local servers and a permission-filtered local MCP server for compatible applications.
- Mapped MCP resources, tools, prompts, notifications, elicitation, and sampling into FAM policy.
- Preserved native APIs, deterministic OS/tool adapters, AT-SPI, and restricted vision/input as non-MCP integration paths.
- Expanded Phase 2, Phase 5, Phase 7, and Phase 14 gates and corrected the stale immediate next step from Phase 1.9 to Phase 2.1.
- Added ADR 0011 for dual hardware validation and ADR 0012 for the MCP connector boundary.

## Explicitly not completed

- No GPU-enabled Ollama service or generalized benchmark composition was implemented.
- No full-workstation model inference benchmark was run.
- No versioned hardware profile or resource-budget schema was created; that begins in Phase 2.2.
- No machine profile artifact containing hostname or device identity was persisted.
- No MCP SDK, client, server, connector package, or network endpoint was added.
- No remote MCP access was approved.
- No running model was loaded, unloaded, downloaded, or changed.

## Architecture and decisions

ADR 0011 prevents the minimum target from becoming an artificial ceiling on the development machine. The constrained and full profiles answer different questions and must remain separately named in configuration, artifacts, and reports. Full capability makes every hardware tier schedulable and measurable but retains explicit Linux and foreground-application headroom.

ADR 0012 keeps FAM_OS protocol-neutral. MCP provides valuable discovery and structured invocation, but all MCP primitives are translated into Application Fabric contracts before Core uses them. An MCP server can advertise a tool; FAM still decides its effects, permission requirement, confirmation, verifier, postconditions, and audit treatment. Transport authorization and FAM user authority remain separate.

The first Application Fabric demonstration now requires an MCP-backed semantic capability and a declared fallback with MCP unavailable. This proves that MCP improves fidelity without becoming a single point of application coverage.

## Files changed

| Path | Purpose |
|---|---|
| `docs/architecture/HARDWARE_VALIDATION_PROFILES.md` | Named profiles, reference snapshot, quality rules, telemetry, and implementation sequence |
| `docs/architecture/MCP_APPLICATION_CONNECTOR.md` | MCP roles, primitive mapping, lifecycle, security boundary, and fallback |
| `docs/architecture/APPLICATION_WEAVING.md` | MCP placement in the existing four-level integration ladder |
| `docs/decisions/0011-dual-hardware-validation-profiles.md` | Durable constrained-versus-full hardware decision |
| `docs/decisions/0012-mcp-application-connector-boundary.md` | Durable protocol-neutral MCP decision |
| `MASTER_PLAN.md` | Expanded Phase 2, 5, 7, and 14 work and corrected immediate step |
| `AGENTS.md` | Dual-profile, storage-semantics, and raw-MCP authority rules |
| `src/fam_os/applications/README.md` | Application component ownership of MCP mapping boundary |
| `docs/PROJECT_STRUCTURE.md` | MCP remains an external adapter dependency |
| `README.md` | Entry points for hardware profiles and MCP architecture; current Phase 1 status |
| `handoffs/README.md` | Handoff 0011 sequence entry |
| `handoffs/0011-full-hardware-and-mcp-plan.md` | This architecture-planning handoff |

## Public interfaces

No runtime interface was added.

The plan now names two future validation-profile identifiers:

- `compat-cpu-16gb`
- `full-reference-workstation`

These names are architectural commitments, not yet versioned configuration. Phase 2 must define their schemas before tools consume them.

MCP is committed as an adapter protocol in two future directions: local MCP servers into the Application Capability Registry and a permission-filtered FAM MCP ingress. Application Fabric contracts, not MCP wire types, remain public domain interfaces.

## Validation

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version,pstate,power.limit \
  --format=csv,noheader,nounits
lscpu
free -b
lsblk -d -b -o NAME,TYPE,SIZE,MODEL,ROTA,TRAN
findmnt -no SOURCE,FSTYPE,SIZE,USED,AVAIL,TARGET /
ollama --version
ollama ps
```

Result: RTX 5080 with 16,303 MiB total VRAM; Intel Core Ultra 9 285K with 24 logical CPUs; 67,017,834,496 bytes RAM; KIOXIA 2,048,408,248,320-byte NVMe; ext4 root with approximately 513.5 GiB available; Ollama 0.30.11. Host swap was in use and is therefore explicitly excluded from service-level conclusions.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: all 105 tests passed in 0.026 seconds; 0 failures.

```bash
rg -n "Begin \*\*Phase 1\.9|Phase 1 migration is now underway" \
  MASTER_PLAN.md README.md docs AGENTS.md
```

Result after correction: no stale implementation-status matches.

Official MCP architecture and authorization documentation was checked against the 2025-11-25 specification before fixing the adapter boundary. FAM_OS documentation deliberately avoids embedding protocol-version-specific wire types into domain contracts.

## Evidence and artifacts

- `docs/architecture/HARDWARE_VALIDATION_PROFILES.md`
- `docs/architecture/MCP_APPLICATION_CONNECTOR.md`
- `docs/decisions/0011-dual-hardware-validation-profiles.md`
- `docs/decisions/0012-mcp-application-connector-boundary.md`
- `docs/architecture/APPLICATION_WEAVING.md`
- Existing constrained baseline: `artifacts/parity/phase1-parity-20260716-095056-252893.json`
- Official MCP architecture: `https://modelcontextprotocol.io/docs/learn/architecture`
- Official MCP authorization specification: `https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization`

## Known limitations and risks

- The workstation values are a live snapshot, not a versioned privacy-reviewed profile artifact.
- Available RAM, VRAM, filesystem space, power state, thermals, and loaded models change between runs.
- The correct OS headroom policy is not yet encoded; Phase 2 must make it explicit rather than hardcode a workstation-specific value.
- Ollama may choose GPU/CPU placement internally unless the adapter can observe or control the required fields; reports must distinguish requested placement from observed placement.
- NVIDIA telemetry does not automatically expose all model-transfer or tensor-placement details.
- SSD I/O and page-cache measurements require careful attribution to avoid claiming unrelated host activity.
- MCP server metadata is not sufficient to prove read-only behavior or safe effects.
- Local stdio servers can inherit secrets or excessive filesystem access if connector packaging and process limits are weak.
- MCP protocol evolution must be isolated in adapters and compatibility tests.

## Operational notes

All hardware probes were read-only. An existing `nomic-embed-text:latest` model was observed resident on the GPU during `ollama ps`; it was not started, stopped, or modified by this work. No systemd unit, cgroup, model store, driver, device permission, network service, or filesystem configuration changed.

## Recommended next entry point

Begin Phase 2.1 with the existing request, routing, application-capability placeholder, execution, and result contracts. Then implement Phase 2.2 so host inventory, effective service limits, OS headroom, CPU, RAM, VRAM, SSD/cache budgets, and validation-profile identity are versioned before the benchmark harness is generalized. Do not build the GPU service or MCP adapters ahead of those provider-neutral contracts.
