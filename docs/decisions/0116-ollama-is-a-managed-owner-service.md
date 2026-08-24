# ADR 0116: Ollama is a managed owner service

Status: Accepted

## Context

The installed product previously depended on an unrelated system Ollama daemon
and model directory. FAM_OS could not own health, resource limits, model
identity, shutdown, or recovery.

## Decision

FAM_OS starts Ollama as the dedicated `fam-ollama.service` in the owner's systemd
manager, bound to an explicit loopback port with a private managed model root.
The service has its own cgroup, health gate, bounded stop, and reconciliation.
Downloaded library models enter the managed store only through manifest parsing
and SHA-256 validation of every referenced blob; safe hard links are preferred
and a private digest-rechecked copy is used when linking is unavailable.

## Consequences

- FAM_OS no longer needs to mutate or stop the system Ollama service.
- Managed and system model stores can coexist.
- A service is not ready merely because its process is active; `/api/tags` must
  pass before Core can use it.
- Release removal owns only `fam-ollama.service` and the FAM model root.

## Evidence

- `src/fam_os/product/composition/managed_ollama.py`
- `src/fam_os/product/composition/ollama_model_import.py`
- `artifacts/product/phase17/managed-ollama.json`
