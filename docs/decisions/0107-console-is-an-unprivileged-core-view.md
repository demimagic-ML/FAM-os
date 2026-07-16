# ADR 0107: Console is an unprivileged Core view

Status: Accepted

FAM Console is a local presentation client, not an authority boundary. It serves
complete resource, expert, permission, memory, audit, and recovery visibility
through typed snapshots. It binds only to loopback, requires a 256-bit private
bearer token for state, and sends no-store and restrictive browser headers. Any
future mutation must call a typed Core command; the HTTP/UI layer must never edit
permission, application, expert, or memory state directly.
