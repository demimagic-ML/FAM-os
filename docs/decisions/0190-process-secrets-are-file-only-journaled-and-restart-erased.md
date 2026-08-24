# ADR 0190: Process secrets are file-only, journaled, and restart-erased

Status: Accepted

## Context

Process, API, and browser environments need opaque credentials, but
`systemd-run --scope` is asynchronous. Deleting materialized files immediately
after launch races Bubblewrap setup, while leaving an unrecorded temporary
directory can leak plaintext after a crash. Passing values in argv or the
outer environment would also expose them through process metadata.

## Decision

The process integration adapter accepts opaque secret references only through
a replaceable provider. Provider output is validated as bounded uppercase
tool keys. Values are written to owner-private, candidate-local files and
Bubblewrap mounts each file read-only under `/run/fam-secrets`. The child
receives only `<KEY>_FILE`; plaintext never enters argv or environment values.

Before asynchronous process launch, the adapter durably appends the relative
secret-root identity to the candidate-local process journal. Normal cleanup,
failed-launch compensation, revocation, and restart reconciliation stop exact
recorded scopes before erasing every recorded root. Cleanup receipts name the
removed root but never its content. Journals from before this decision are
accepted with an empty normalized `secret_roots` list.

Because the complete candidate is mounted at `/workspace`, Bubblewrap shadows
`/workspace/.fam/secret-injection` with an empty tmpfs. A service can see only
its explicitly mounted `/run/fam-secrets` files, not sibling service roots.
Secret roots are never retained artifacts.

Product composition passes one provider to Docker and process backends but
still defaults to denial. Production secret use remains unavailable until an
authenticated owner-controlled encrypted provider/reference lifecycle is
composed; installed adapter tests do not substitute for that missing authority.

## Consequences

- Restart can erase plaintext without persisting plaintext or replaying use.
- Revocation after launch terminates the process tree and removes files.
- Same-UID host processes remain inside the Linux owner trust boundary and can
  inspect mode-0600 files while active; stronger isolation requires a
  privileged credential broker or kernel keyring design.
- A provider returning invalid, empty, ambient-loader, or path-controlling keys
  fails before process effect.

## Evidence

- `src/fam_os/adapters/integration/process_secrets.py`
- `src/fam_os/adapters/integration/process_state.py`
- `src/fam_os/adapters/integration/process_environment.py`
- `src/fam_os/product/composition/integration_environment.py`
- `tests/unit/test_process_integration_environment.py`
- `tests/unit/test_process_environment_state.py`
- `tests/integration/test_process_api_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt7.json`
