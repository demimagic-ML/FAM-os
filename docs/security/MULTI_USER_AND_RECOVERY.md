# Multi-user isolation and recovery mode

FAM_OS runs separately for each Linux user. It does not share a Core process,
memory database, permission store, audit ledger, connector credentials, release
pointer, or recovery state between users. Private roots require the effective UID
and mode 0700. Root and a compromised same-user account remain outside this
filesystem permission claim.

Recovery mode starts without application connectors, remote fabric, model
runtimes, or training services. It can inspect diagnostics, export owner data,
repair deterministic indexes, and roll back to a healthy signed release. It
cannot execute application actions or silently reconstruct permissions.
