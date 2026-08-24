# ADR 0226: Isolated PostgreSQL migrations use non-superuser streamed verification

Status: Accepted

## Context

ADR 0225 made a fixed, secret-bound PostgreSQL 17 service reachable from the
natural integration lifecycle, but service health did not prove a migration.
Phase 27.12 requires forward and rollback execution, backup/restore,
transaction behavior, and schema/data evidence without turning model output
into administrative SQL or exposing a database endpoint.

A physical experiment also showed that `docker cp` cannot write into the
read-only container root even when `/tmp` is a tmpfs. Weakening the read-only
root or writing plaintext migration/backup material to shared temporary paths
would reduce the existing boundary.

## Decision

Natural PostgreSQL migration verification is candidate-only and accepts at
most four exact forward/reverse SQL pairs. Every asset is a current regular
single-link candidate file with a bound digest and size. PostgreSQL meta
commands and role, user, database, tablespace, `ALTER SYSTEM`, session-role,
`COPY PROGRAM`, and `LOAD` administration are rejected before execution.

The trusted runtime creates only fixed database `fam_candidate` and fixed role
`fam_migrator`. The role must physically report `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOINHERIT`, `NOREPLICATION`, and `NOBYPASSRLS`. Migration SQL
runs as that role in a single transaction.

Bounded SQL and decrypted backup bytes are streamed to fixed `psql` and
`pg_restore` argv through the Docker client. No shell, host port, connection
string, bind-mounted plaintext secret, writable container root, or model-
selected command is introduced.

The verifier records baseline schema/data digests, encrypts the retained
custom backup, applies forward migrations, probes transaction rollback,
reverses to the exact baseline, reapplies to the exact first state, and restores
the baseline into a fresh database. Failure attempts candidate recovery from
the encrypted baseline. The plan and successful receipt must bind the exact
service, runtime, permit, authority decisions, candidate, and changeset before
preview and are repeated against a fresh owner clone after apply.

## Consequences

- A natural PostgreSQL task can prove a reversible isolated migration rather
  than merely prove container health.
- The migration role cannot administer the cluster or production resources.
- Plaintext SQL and backup content do not require a host temporary file.
- A restart after verification but before durable changeset attachment does
  not replay success; the recovered environment is cleaned and fails closed.
- This does not create an external/remote/production database adapter, expose
  a host port, or provide MySQL support.

## Alternatives considered

- Run migrations as the PostgreSQL superuser: rejected because it makes
  candidate SQL an administrative capability.
- Use `docker cp`: rejected by the physical read-only-root result.
- Make the container root writable: rejected because verification does not
  justify weakening the fixed service.
- Mount plaintext SQL or backups from the host: rejected because bounded stdin
  and encrypted retained artifacts provide a narrower boundary.
- Call this production database support: rejected because all effects remain
  inside the isolated fixed service.

## Evidence

- `src/fam_os/core/engineering/postgresql_verification.py`
- `src/fam_os/core/engineering/postgresql_verification_service.py`
- `src/fam_os/adapters/database/postgresql_planning.py`
- `src/fam_os/adapters/database/postgresql_admission.py`
- `src/fam_os/adapters/database/postgresql_commands.py`
- `src/fam_os/adapters/database/postgresql_verification.py`
- `src/fam_os/adapters/database/postgresql_storage.py`
- `tests/integration/test_natural_postgresql_environment.py`
- `artifacts/product/phase30/natural-postgresql-migration-install-20260719-01/evidence.json`
