# ADR 0223: Natural service declarations are versioned intent-subordinate data

Status: Accepted

## Context

ADR 0222 safely composed two fixed service templates, but the planner inferred
their logical identities and dependency from keywords and candidate files. That
does not scale to a visible design artifact and gives the model no typed way to
propose a service graph. Accepting Docker Compose, shell commands, framework
scripts, recipe coordinates, or an open-ended manifest would let untrusted
candidate content choose executable policy or new authority.

FAM_OS configuration is required to be versioned data, and model output is
always untrusted. A natural task therefore needs a declarative vocabulary that
can express topology while remaining subordinate to the owner's admitted
request and Core's release-owned template selection.

## Decision

Core defines the public exact-version contract
`fam.core.natural-integration-declaration/v1alpha1`. Its candidate filename is
fixed as `fam.integration.json`. The complete document uses the standard
self-describing schema envelope and contains only:

- a declaration identity;
- one or more unique logical service identities;
- a closed template enum (`python_api` or `static_site`); and
- dependency identities forming an acyclic graph.

The initial release supports each fixed template at most once. Service IDs are
bounded lowercase identifiers, dependencies must refer to another declared
service, self-dependencies and cycles fail, unknown/duplicate fields and JSON
keys fail through the strict schema codec, and the entire UTF-8 regular file is
bounded to 65,536 bytes and opened without following symlinks.

The declaration never contains commands, executable paths, recipe coordinates,
ports, network destinations, images, volumes, secrets, health policy, budgets,
or authorities. The natural planner maps each enum to a release-signed fixed
template, maps logical dependencies to phase-specific service IDs, and derives
ports and health checks itself.

Candidate data cannot expand admitted intent. A `python_api` declaration is
accepted only when the owner's natural request explicitly asked for an API,
backend, full-stack app, or web service. An API-only request cannot implicitly
run a static site. A request naming a site/page/full-stack surface cannot omit
the static service. Missing regular `api.py` or HTML inputs fail truthfully.

For a natural integration task, the generation prompt exposes the declaration
schema, filename, closed template names, and a complete example. It explicitly
describes roles rather than recipes. Recipe coordinates remain absent from
model context. The generated declaration is an ordinary candidate file, so it
appears in the exact changeset, owner checkpoint, apply, Git commit, and
rollback scope. Post-apply planning reloads it from the fresh owner clone.

## Consequences

- Natural language can produce an owner-visible typed service topology without
  controlling execution mechanics.
- The same strict document is validated before candidate and post-apply runs;
  schema drift or owner-tree substitution fails.
- A full-loop integration proves a model-proposed declaration is previewed,
  applied, decoded from the owner tree, rerun, and committed.
- The schema catalog grows from 414 to 415 generated roots.
- The initial enum remains intentionally narrow; adding a template requires a
  release-owned implementation, tests, and a superseding contract decision.
- External network, secrets, containers, browsers, databases, clusters, and
  dynamic-port ownership remain separate powers and are not implied.

## Alternatives considered

- Continue keyword-only inference: rejected as insufficiently visible and
  non-extensible for a master engineering lifecycle.
- Accept Docker Compose or framework command files: rejected because those are
  executable inputs, not bounded authority-neutral topology.
- Put recipe IDs in the declaration: rejected because trusted Core, not model
  output or repository data, selects installed recipes.
- Let a declaration widen a vague `end-to-end` request: rejected because
  candidate data is subordinate to the admitted owner intent.

## Evidence

- `src/fam_os/core/engineering/natural_integration_declaration.py`
- `src/fam_os/adapters/integration/natural_declaration.py`
- `src/fam_os/adapters/integration/natural_planning.py`
- `src/fam_os/core/engineering/candidate_generation_service.py`
- `schemas/v1alpha1/fam.core.natural-integration-declaration.schema.json`
- `tests/unit/test_natural_integration_environment.py`
- `tests/unit/test_candidate_generation_service.py`
- `tests/integration/test_natural_integration_environment.py`
- `tests/contract/test_schema_roundtrip.py`
