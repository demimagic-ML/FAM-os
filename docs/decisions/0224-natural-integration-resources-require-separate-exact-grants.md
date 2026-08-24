# ADR 0224: Natural integration resources require separate exact grants

Status: Accepted

## Context

ADR 0223 intentionally excludes network destinations, secret references,
budgets, and authorities from `fam.integration.json`. The natural API already
identified `network` and `secret_use` as separately confirmed authorities, but
it stopped every such request because there was no exact owner ceremony or
path from that ceremony to the integration planner. Adding these resources to
the ordinary task grant, accepting them from candidate/model content, or
silently attaching configured credentials would collapse the observation,
proposal, approval, and execution boundaries.

The existing integration service can enforce exact network endpoints and
opaque secret references, but it previously received only the ordinary task's
single grant ID. Natural composition therefore needs a resource-specific grant
that remains subordinate to the original owner words and can satisfy every
live authorization request without widening the ordinary task.

## Decision

Natural integration network and secret resources use a second existing
`EngineeringAuthorityGrant`, never fields in the service declaration and never
model-selected executable data.

Core derives this grant only when all of the following hold:

- the request explicitly asks for a natural integration environment;
- network intent uses one or more explicit canonical
  `network access to <host-or-IP>:<port>`, `network host`, or equivalent bounded
  forms;
- secret intent names one or more explicit `secret ref`, `secret reference`,
  or `secret named` identifiers; and
- every extracted endpoint passes the existing canonical integration-network
  validator.

Generic words such as `network` or `secret` without their exact resources
remain visible high-risk intent but produce no grant and cannot activate.
Unrelated colon-delimited text is not treated as a destination.

The supplemental grant is:

- deterministically identified from the primary grant;
- non-inheritable, active for the same bounded task lifetime, and scoped to the
  exact owner, principal, task, workspace, and `integration-environment`
  toolchain;
- limited to `execute` plus only the requested `network` and/or `secret_use`
  authorities;
- limited to the exact destinations and secret references from the original
  natural intent;
- limited to 16 MiB of network transfer when network is requested; and
- `opaque_credential_injection` for secret references, never model-visible
  disclosure.

The owner sees the complete grant envelope, resource list, byte limit, and
grant digest through Console or Shell and approves it in a distinct
authenticated transport-session ceremony before approving the ordinary task
grant. The supplemental grant is persisted through the existing owner-encrypted
grant repository. Natural proposal storage advances to record format v2 to
retain its exact grant; v1 records remain readable and contain no supplemental
grant.

Before every candidate or post-apply environment, the product resolves only a
currently usable supplemental grant. The deterministic planner re-extracts the
resources from the immutable original task intent and rejects a different
grant identity, authority set, owner/principal/task/workspace, toolchain,
destination, secret reference, exposure policy, or network budget. It assigns
opaque secret references only to the fixed Python API role. The resulting plan
uses the existing allowlisted-network and secret-injection enforcement paths,
and `IntegrationEnvironmentService` authorizes execute, every destination, and
every reference against that one exact supplemental grant.

Active grants continue to require owner reconfirmation after service restart.
No network session, broker handle, or secret value enters Core, model context,
the natural proposal, Console/Shell output, or `fam.integration.json`.

## Consequences

- A user can request bounded network and opaque-secret use in natural language
  without giving the ordinary engineering task either authority.
- Console and Shell present two distinct checkpoints: exact integration
  resources first, ordinary repository authority second.
- Candidate/model output cannot add a host or secret; planner re-derivation
  rejects tampered or stale grants before launch.
- Candidate and fresh-owner post-apply environments use the same resource
  semantics and persistent grant boundary.
- The existing 415 schema roots are unchanged because the public grant schema
  is reused; only encrypted natural-proposal storage advances to v2 with v1
  read compatibility.
- Actual secret provisioning, rotation, revocation across all backends, broker
  availability, remote-database composition, and installed/live qualification
  remain separate requirements.

## Alternatives considered

- Add network and secret fields to `fam.integration.json`: rejected because
  model/candidate data must not request new authority.
- Widen the primary natural task grant: rejected because a single confirmation
  would silently combine ordinary repository effects with external or
  credential-bearing effects.
- Accept any hostname-looking token in the prompt: rejected because unrelated
  times, ports, or examples could become authority. The syntax must explicitly
  name a network destination.
- Configure one ambient integration credential or network session: rejected
  because it is neither task/resource scoped nor auditable as owner intent.
- Pass different grant IDs per authorization request: deferred as unnecessary
  for this bounded slice; one exact supplemental task grant safely contains
  execute plus only its network/secret resources.

## Evidence

- `src/fam_os/core/engineering/natural_integration_resources.py`
- `src/fam_os/core/engineering/natural_language.py`
- `src/fam_os/adapters/sqlite/natural_engineering_serialization.py`
- `src/fam_os/adapters/integration/natural_resource_planning.py`
- `src/fam_os/adapters/integration/natural_planning.py`
- `src/fam_os/product/natural_engineering_integration_authority.py`
- `src/fam_os/product/natural_engineering_integration.py`
- `src/fam_os/console/natural_engineering_routes.py`
- `src/fam_os/console/static/natural_engineering.js`
- `src/fam_os/adapters/shell/natural_engineering.py`
- `tests/unit/test_natural_language_engineering.py`
- `tests/unit/test_product_natural_engineering_api.py`
- `tests/unit/test_natural_integration_environment.py`
- `tests/unit/test_fam_shell_natural_engineering.py`
- `tests/integration/test_console_natural_engineering.py`
