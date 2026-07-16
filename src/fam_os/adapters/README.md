# Adapters ownership

Owns replaceable integrations with Ollama, Linux hardware discovery, systemd, cgroups, filesystems, devices, and future inference runtimes.

Each technology gets its own subpackage when its migration step begins. Adapters implement application ports and do not contain product policy.

Implemented adapters:

- `linux/`: read-only host hardware discovery for Phase 1.5.
- `ollama/`: non-streaming chat, loaded-model inspection, and unload for Phase 1.6.
- `systemd/`: user-scoped transient service lifecycle for Phase 1.7.
- `cgroup/`: read-only cgroup-v2 resource observation for Phase 1.7.
- `bubblewrap/`: explicit isolated Python sandbox execution for Phase 1.8.
- `audit/`: locked, private, append-only JSONL SHA-256 audit chain for Phase 3.5.
- `mcp/`: local official-SDK client, approved primitive mapping, schema checks,
  bounded invocation, and Application Fabric registrations for Phase 5.3.
- `filesystem/`: bounded strict local expert-manifest discovery for Phase 6.2
  and private locked atomic expert-residency state for Phase 7.3.
- `crypto/`: detached Ed25519 package signature verification for Phase 6.3.
