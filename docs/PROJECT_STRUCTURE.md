# FAM_OS Project Structure

This is the intended structure. Implementation directories should be created only when their phase begins and each must contain a local ownership README.

```text
FAM_OS/
├── AGENTS.md
├── MASTER_PLAN.md
├── README.md
├── configs/                 Versioned runtime and policy configuration
├── docs/
│   ├── architecture/        Current architecture descriptions
│   ├── decisions/           Append-only ADRs
│   ├── protocols/           Public schemas and protocols
│   ├── security/            Threat models and permission boundaries
│   └── operations/          Installation and operational procedures
├── handoffs/                Append-only major-change history
├── clients/                 FAM Shell, Console, CLI, and SDK clients
├── packages/                Expert, verifier, and connector package definitions
├── schemas/                 Machine-validated versioned schemas
├── src/fam_os/
│   ├── supervisor/          Minimal deterministic privileged boundary
│   ├── core/                Request lifecycle and coordination
│   ├── routing/             Capability, complexity, and escalation policy
│   ├── experts/             Expert contracts and lifecycle
│   ├── scheduler/           Placement, budgets, cache, and neural paging
│   ├── verification/        Verifier orchestration and sandbox adapters
│   ├── memory/              Permissioned memory and retrieval
│   ├── applications/        Capabilities, observations, actions, and connectors
│   ├── registry/            Signed package registry
│   ├── schemas/             Serialization, compatibility, and reference mechanics
│   ├── telemetry/           Metrics and audit events
│   └── adapters/            Models, Linux, apps, accessibility, devices, storage
├── tests/
│   ├── unit/                Component-local behavior
│   ├── contract/            Schema and adapter compatibility
│   ├── integration/         Multi-component workflows
│   ├── hardware/            Named hardware-profile tests
│   └── security/            Permissions, sandbox, and adversarial cases
└── tools/                   Small development and benchmark entrypoints
```

## Dependency direction

```text
Adapters -> application interfaces -> domain contracts
Clients  -> local API -> application use cases -> domain contracts
Runtime  -> public component contracts only
```

Core contracts must not import Ollama, systemd, GPU, database, filesystem-command, MCP, accessibility, desktop-control, UI, or web-client implementations.

Application Fabric policy belongs in `applications/`. MCP, other native connectors, and generic desktop bridges implement its public contracts through separate adapter modules. A FAM client may request or display an action but cannot grant permission or execute around Core policy.

## File placement test

Before adding a file, answer:

1. Which master-plan step owns it?
2. Which component has the responsibility?
3. What public contract does it implement or expose?
4. Where are its focused tests?
5. Would its name remain meaningful if Ollama or Linux tooling were replaced?

If these questions do not have clear answers, do not add the file yet.
