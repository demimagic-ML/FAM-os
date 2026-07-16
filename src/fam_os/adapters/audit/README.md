# Supervisor audit adapter ownership

Owns durable local encoding mechanics for privacy-bounded Supervisor audit events. The JSONL adapter locks the file, verifies the complete SHA-256 chain before each append, writes one canonical record with `O_APPEND`, calls `fsync`, and rejects symlinks, non-regular targets, wrong ownership, and group/world permissions.

The adapter is tamper-evident, not tamper-proof against the file owner or root. It does not decide which operations require audit, invent caller identity, accept free-form payloads, or silently downgrade a required write.
