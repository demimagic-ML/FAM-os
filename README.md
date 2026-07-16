# FAM_OS — For All Mankind Operating System

![FAM_OS profile photo](FamOS.jpeg)

FAM_OS is an **always-on operating-system intelligence service** built above the Linux kernel. It weaves together local models, your real hardware, the applications you already use, deterministic tools, memory, and trusted devices into one supervised, privacy-first intelligence fabric.

> **FAM_OS is not an LLM living inside the Linux kernel.** Linux still owns hardware, processes, memory, filesystems, networking, and drivers. FAM_OS adds a thin deterministic supervisor and unprivileged user-space services on top.

```text
Linux kernel
  -> FAM Supervisor          (minimal, deterministic, privileged)
  -> FAM Core                (unprivileged request lifecycle)
  -> Application Fabric       (existing apps as capabilities)
  -> Expert, Verification, Memory, and Hardware fabrics
```

A simple way to think about it: FAM_OS makes your whole PC itself intelligent, while keeping every action **scoped, approved, verified, and auditable**.

---

## What problem does it solve?

Today's AI assistants are usually one of the following:

- **Cloud chatbots** that cannot touch your local files, apps, or hardware.
- **IDE extensions** that understand code but not the rest of your desktop.
- **Screen-control agents** that click and type by watching pixels, with no real understanding of application state.
- **New AI-native operating systems** that want to replace the kernel and start from scratch.

FAM_OS takes a different path: **augment the Linux desktop you already have**. It turns existing programs into permissioned AI capabilities, verifies results before showing them to you, and schedules work across your CPU, RAM, GPU/VRAM, and SSD with explicit resource budgets.

---

## A simple, everyday example

You type into the FAM Shell:

> "Summarize the first five pages of the PDF in my Downloads folder and save a one-paragraph summary to my Desktop as `summary.txt`."

FAM_OS:

1. **Discovers** the Downloads and Desktop folders through scoped file capabilities.
2. **Extracts** the PDF text using a deterministic tool rather than guessing from a screenshot.
3. **Asks** you to confirm it can create `summary.txt` on the Desktop.
4. **Writes** the file only after you approve.
5. **Verifies** the file exists, is not empty, and matches the expected scope.
6. **Returns** the summary and records the action in the audit log.

---

## A concrete example

You type into the FAM Shell:

> "Refactor `stable_topological_sort` so it handles neighbor-only nodes and preserves input order, then run the tests and commit."

FAM_OS:

1. **Admits** your request to FAM Core with your current permission context.
2. **Observes** the active VS Code: editor through a native semantic connector and the test file through a scoped file adapter.
3. **Plans** a workspace edit, a test run, and a git commit.
4. **Asks** you to approve the edit and commit before executing — they are externally consequential.
5. **Executes** through the narrowest adapter: VS Code: connector, deterministic tool runner, and git.
6. **Verifies** postconditions: tests pass, file hash changed, working tree is clean.
7. **Returns** a verified result and writes an audit event.

If the VS Code: extension is not running, the same task degrades gracefully: FAM_OS reads the file directly, edits through the file adapter, runs tests, and tells you it used reduced-fidelity mode.

---

## The landscape — what else exists?

FAM_OS overlaps with several active areas. None of the projects below is a direct equivalent, but they cover pieces of the same space.

| Category | Example projects | What they do | How FAM_OS differs |
|---|---|---|---|
| **AI-native / cognitive OS** | [Aegis-Core](https://github.com/Gustavo324234/Aegis-Core), [XKernel](https://github.com/JosephBerm/XKernel) | Treat agents as first-class kernel/cognitive processes with scheduling, memory, and capability security. | FAM_OS **does not replace Linux or the kernel**. It adds a minimal deterministic supervisor and an unprivileged Core on top, so it can run on a normal desktop today. |
| **Desktop computer-use agents** | [Open Computer Use](https://chatgate.ai/post/open-computer-use), [Cua](https://cua.ai/), [Open Interpreter](https://github.com/openinterpreter/openinterpreter/), [computer-agent](https://github.com/suitedaces/computer-agent) | Drive the desktop by screenshots, accessibility trees, cursor, and keyboard. | FAM_OS treats screen/input as the **last rung of a ladder**, not the default. It prefers native semantic connectors and deterministic OS/tool adapters, and it verifies results rather than trusting vision-only actions. |
| **Coding agents / IDE assistants** | [Cline](https://github.com/Cline/Cline), Claude Code, Cursor, GitHub Copilot | Assist inside the editor with code generation, commands, and MCP tools. | FAM_OS is **OS-level**, not editor-level. It can coordinate VS Code:, a terminal, a browser, a file manager, and a test runner into one verified cross-application task. |
| **AI agent workspaces** | [Wegent](https://github.com/wecode-ai/Wegent), Dify, Flowise | Self-hostable chat/knowledge/automation workspaces with connectors. | Workspaces are usually chat-first or workflow-first. FAM_OS is a local **service fabric** woven into the Linux desktop, with explicit hardware scheduling, verification, audit, and application adapters. |
| **Agent security & capability layers** | [agent-kernel](https://github.com/dgenio/agent-kernel), AgentFence, contextweaver, [Cord](https://github.com/fosenai/cord) | Provide capability tokens, policy enforcement, audit traces, context selection, or decentralized capability discovery. | FAM_OS includes similar safety concerns but wraps them in a complete runtime: Linux hardware discovery, cgroup scheduling, verified execution, application weaving, local memory, and a terminal Shell. |
| **MCP tooling** | [mcp-cli / mcps](https://github.com/iTzFaisal/mcp-cli) | Discover, install, and manage MCP servers across agents. | MCP is **one replaceable adapter** in FAM_OS, not the product. The internal Application Fabric contracts are protocol-agnostic. |
| **Local inference stacks** | Ollama, vLLM, llama.cpp | Serve open models locally. | FAM_OS orchestrates intelligence *above* them; it does not replace them. |

*Comparisons are based on publicly available documentation and source code. They are intended to clarify positioning, not to claim feature parity or superiority in every dimension.*

---

## What makes FAM_OS different?

The combination below is the project's core bet:

| Principle | Why it matters |
|---|---|
| **Above Linux, not replacing it** | Uses the real kernel, cgroups, namespaces, and systemd. No new microkernel required. |
| **Deterministic supervisor + unprivileged Core** | Models never run inside the privileged supervisor or kernel. |
| **Verification-first** | Every result or action must satisfy a declared acceptance policy before it is released to you. |
| **Observation ≠ action** | Seeing an app does not grant permission to change it. |
| **Application weaving ladder** | Native semantic → OS/tool → accessibility → screen, degrading gracefully rather than defaulting to screenshots. |
| **Resource-aware scheduling** | CPU/RAM/GPU-VRAM/SSD budgets with a constrained `compat-cpu-16gb` baseline and a `full-reference-workstation` profile. |
| **MCP as an adapter** | Not locked into one connector protocol. |
| **Local-first and privacy-reviewed** | Workstation captures scrub identifiers and retain failed baselines as evidence. |
| **Audit + approval as first-class** | Every action carries scope, reversibility, confirmation policy, and an audit event. |

---

## Current status

FAM_OS is a working prototype, not a packaged product.

- **Phases 1–6 are complete.** This includes the FAM Shell terminal UI, the Application Fabric, MCP client/server adapters, Linux accessibility and discovery bridges, deterministic tool adapters, action safety, a real cross-application acceptance demo, and the Expert Fabric manifest schema, capability namespace, and local registry.

Full architecture records, implementation handoffs, and decision records are kept inside the repository under `docs/` and `handoffs/`.

## Future work

- **Phase 7 — Hardware scheduler and neural pager:** Turn context length and model residency into scheduled memory allocations across CPU, RAM, GPU/VRAM, and SSD cache.
- **Phase 8 — Verification Fabric:** Plug-in verifier packages, deterministic sandbox policy, and stronger postcondition checking.
- **Phase 9 — Multi-task Expert Fabric:** Smaller, swappable experts coordinated by a router instead of one giant model per request.
- **Phase 10 — Memory and retrieval fabric:** Permissioned short-term and long-term memory with provenance and retrieval.
- **Phase 11 — Local adaptation and predictive behavior:** Learn from your workflows without baking personal data into model weights.
- **Phase 12 — Trusted multi-device fabric:** Extend the same supervised boundary to trusted local devices.
- **Phase 13 — Expert Factory and hardware-aware training:** Tools to build, verify, and optimize experts for the target machine.
- **Phase 14 — Reliability, security, and productization:** Hardening, packaging, and making FAM_OS installable as a real local service.

---

## Quick start for readers

1. Read the architecture overview in `docs/architecture/APPLICATION_WEAVING.md`.
2. Read the MCP boundary in `docs/architecture/MCP_APPLICATION_CONNECTOR.md`.
3. Read the hardware profiles in `docs/architecture/HARDWARE_VALIDATION_PROFILES.md`.
4. Read the latest handoff in `handoffs/`.
5. Run the test suite: `PYTHONPATH=src:. python3 -m unittest discover -s tests`

---

## License

See the repository's `LICENSE` file for the exact terms.
