# Handoff 0261: Natural PostgreSQL service composition

**Date:** 2026-07-19  
**Plan step:** Source portions of Phase 27.12, 27.13, 27.16, 30.1, and 30.5  
**Status:** Partial (`source_composed`; service lifecycle only)  
**Previous handoff:** `0260-natural-integration-resource-ceremony.md`

## Objective

Make the existing digest-pinned PostgreSQL integration backend reachable from
natural owner intent through the exact ADR 0224 resource ceremony without
accepting model-selected executable or credential configuration.

## Scope completed

- Added `postgresql` to the closed natural service-role declaration.
- Added intent-subordinate implicit and declared-role admission; a declaration
  cannot add PostgreSQL unless the owner request explicitly asks to run it.
- Mapped the role to one release-owned cached PostgreSQL 17 image digest, no
  candidate argv, the signed `pg_isready` health recipe, bounded memory/CPU/PIDs,
  and a 256 MiB ephemeral tmpfs data volume.
- Required exactly one owner-named opaque PostgreSQL password reference and a
  separate `secret_use` resource approval.
- Re-derived and compared the complete supplemental resource impact before
  plan creation, closing storage/process/tool-budget expansion as well as
  network expansion.
- Added role-scoped natural secret assignment. Graphs with both API and
  PostgreSQL secrets require every ref to say `API secret ref ...` or
  `PostgreSQL secret ref ...`; ambiguous or multi-consumer refs fail closed.
- Added adapter-owned stable consumers selected only after matching a trusted
  fixed recipe/image identity. Natural PostgreSQL uses
  `integration:postgresql` and natural Python API uses
  `integration:python-api`; other plans retain the phase-suffix fallback. No
  new consumer field enters candidate data or the public service contract.
- Exposed the ephemeral-storage ceiling and PostgreSQL consumer/tool-key
  convention at the Console and Shell resource checkpoint.
- Prevented the SQLite-only planner from claiming explicit PostgreSQL/MySQL
  requests.
- Added a real Docker integration that starts through Core's exact execute and
  per-ref secret authorization, proves file-only secret injection and signed
  health, then removes the container/network with no leftovers.

## Explicitly not completed

- No SQL migration, typed remote connection endpoint, backup, restore,
  transactional test, schema/data receipt, or database post-apply mutation was
  added.
- No host port is published. The tested internal Docker network does not expose
  the port even when Docker accepts publication metadata.
- No production database, live service, active release, secret value, host
  policy, or owner repository was changed.
- MySQL, a signed installed candidate, live Console/Shell proof, enforced
  profiles, soak, and independent human review remain open.

## Architecture and decisions

ADR 0225 keeps image, command, health, secret consumer, and resource policy in
a trusted fixed adapter template. Candidate declarations still contain only
logical role IDs and dependencies. PostgreSQL health is service evidence, not
database-migration evidence. A remote target remains deferred until a brokered
endpoint and database executor can preserve the existing plan/backup/verify/
restore contract.

The former 363-line natural planner was decomposed into 185-line planning and
187-line intent/template selection modules. New implementation modules remain
below the project size target.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/natural_integration_declaration.py` | Closed PostgreSQL role |
| `src/fam_os/core/engineering/natural_language.py` | Recognize explicit PostgreSQL service execution |
| `src/fam_os/core/engineering/natural_integration_resources.py` | Exact 256 MiB supplemental storage impact |
| `src/fam_os/core/engineering/__init__.py` | Public exact resource-impact helper |
| `src/fam_os/adapters/database/sqlite_planning.py` | Exclude explicitly remote engines |
| `src/fam_os/adapters/integration/postgresql_template.py` | Fixed image/health/volume/consumer mapping |
| `src/fam_os/adapters/integration/natural_template_identity.py` | Shared immutable template and consumer identities |
| `src/fam_os/adapters/integration/natural_template_selection.py` | Intent-subordinate role selection |
| `src/fam_os/adapters/integration/natural_resource_planning.py` | Role-scoped refs and full budget equality |
| `src/fam_os/adapters/integration/natural_planning.py` | Compose PostgreSQL and mixed graphs |
| `src/fam_os/adapters/integration/secret_consumer.py` | Stable explicit/fallback consumer identity |
| `src/fam_os/adapters/integration/docker_service.py` | Use plan-bound consumer identity |
| `src/fam_os/adapters/integration/process_secrets.py` | Use plan-bound consumer identity |
| `src/fam_os/product/composition/integration_environment.py` | One shared PostgreSQL health recipe constant |
| `src/fam_os/console/static/natural_engineering.js` | Resource storage and secret binding display |
| `src/fam_os/adapters/shell/natural_engineering.py` | Resource storage and secret binding display |
| `schemas/v1alpha1/fam.core.natural-integration-declaration.schema.json` | Regenerated closed-role schema |
| `tests/unit/test_natural_integration_environment.py` | Planning, scoping, budget, and post-apply regressions |
| `tests/unit/test_fam_shell_natural_engineering.py` | Complete resource projection fixture |
| `tests/integration/test_natural_postgresql_environment.py` | Real Core/Docker PostgreSQL lifecycle |

## Public interfaces

- `NaturalIntegrationServiceTemplate.POSTGRESQL = "postgresql"`.
- Natural resource approval text now includes maximum ephemeral integration
  storage and the fixed PostgreSQL consumer/tool-key convention.
- The integration service public contract remains unchanged. The schema
  catalog remains 415 roots; the natural-declaration enum expands compatibly.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_natural_integration_environment \
  tests.unit.test_natural_language_engineering \
  tests.unit.test_natural_engineering_store \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_integration_environment_composition \
  tests.unit.test_docker_integration_environment \
  tests.unit.test_process_integration_environment \
  tests.integration.test_natural_integration_environment \
  tests.integration.test_natural_multi_service_process \
  tests.integration.test_natural_postgresql_environment \
  tests.integration.test_console_natural_engineering \
  tests.unit.test_fam_shell_natural_engineering \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.unit.test_integration_environment_repository \
  tests.unit.test_product_integration_environment_api \
  tests.unit.test_mixed_integration_environment \
  tests.unit.test_integration_environment_router \
  tests.integration.test_docker_integration_environment \
  tests.integration.test_real_mixed_integration_environment -q
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Results:

- 121 affected tests pass, including real natural PostgreSQL and the existing
  real API/static and mixed-Docker paths.
- All 41 architecture tests pass.
- All 415 generated schemas validate; JavaScript syntax and diff checks pass.
- Complete discovery executes 1,856 tests. The stable 15 production verifier,
  remote, canary, and gateway failures remain downstream of the absent
  root-owned `fam-os-userns` profile. Two order/timing-sensitive MCP assertions
  and one Shell workflow assertion also appeared across two full-suite runs;
  all three pass immediately as an isolated four-test regression. They are not
  used as evidence of this slice's passage.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T14-17-48-130Z.log`

## Failed experiment and cleanup

Two exact diagnostic PostgreSQL containers/networks tested dynamic and explicit
loopback publication on `--internal` Docker networks. Docker stored
`HostConfig.PortBindings` but reported no public port and null runtime port
mapping. Both containers and both networks were removed. The final real test
uses no host port and leaves no container or network.

## Known limitations and risks

- `POSTGRESQL_IMAGE_SHA256` is the already-qualified cached local image content
  identity; cross-architecture installation needs its own signed profile row.
- The resource UI describes the fixed PostgreSQL consumer even for requests
  that contain only API secrets; a later projection can make role requirements
  conditional without changing authority.
- The integration plan can order a PostgreSQL and Python API graph, but no
  database endpoint or non-secret connection setting is injected into the API.
- The complete suite has pre-existing host-policy failures and demonstrated
  cross-test interference; final qualification must use a clean frozen
  installed candidate and isolated scenario state.

## Recommended next entry point

Add a typed, non-production PostgreSQL attachment contract whose endpoint is
created and attested by a trusted integration broker, then implement a
PostgreSQL migration executor that reuses the existing exact migration pairs,
backup/restore, transaction tests, compensation, and database receipt lifecycle.
Do not publish a raw Docker port or treat the password ref as a connection URL.
