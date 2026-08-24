# ADR 0222: Natural multi-service plans use release-owned fixed templates

Status: Accepted

## Context

ADR 0221 attached one static HTTP preview to the natural engineering loop. The
underlying process adapter already supports dependency-ordered services, but
the natural planner had no safe way to request more than one. Accepting a
command, executable path, recipe coordinate, port, or arbitrary service
manifest from model output would let untrusted candidate content influence the
execution boundary.

The previously shipped Python API integration recipe points at
`/workspace/.fam/services/api.py`. Candidate creation and editing deliberately
exclude `.fam`, so that owner-controlled low-level recipe cannot serve as a
model-created natural engineering entry point.

## Decision

The release adds a second named Python API recipe,
`integration.python.root-api@1.0.0`. Its executable and complete argument
template are fixed and signed with the release: `/usr/bin/python3` runs only
`/workspace/api.py` with the exact `{port:api}` placeholder. The existing
static recipe remains fixed to Python's module server and the candidate root.

The natural planner may select the root API template only when all of the
following hold:

- the already-admitted natural integration request explicitly says `api`,
  `backend`, `full-stack`, or `web service`;
- the exact candidate contains a regular, non-symlink root `api.py`;
- the task owns `execute` authority and its internal
  `integration-environment` tool coordinate;
- Core allocates one distinct loopback port per service; and
- no external destination, secret reference, volume, retained artifact, or
  model-provided argument is present.

When a regular HTML file is also present, Core emits an API service followed by
a static service whose dependency is the API. The existing process adapter
launches and health-checks that topological order. API health is fixed at
`/health`; static health is the exact candidate HTML path. The complete service
tuple remains bound to the environment-plan digest, prospective changeset,
READY receipt, terminal cleanup receipt, fresh post-apply run, and commit.

The natural coordinator asks the planner for the exact required port count,
allocates that many unique ports, and fails before environment admission on a
collision. The existing prelaunch port race is not claimed solved.

## Consequences

- A natural full-stack request can exercise a candidate Python API and static
  page together without granting raw shell or allowing model-selected recipes.
- The model can create or edit normal repository file `api.py`; it still cannot
  modify FAM's protected `.fam` execution metadata.
- A missing or symlinked root API entry point fails truthfully instead of
  silently downgrading an explicitly requested API test to static-only.
- A real Bubblewrap/systemd test proves both signed templates become healthy in
  dependency order and both scopes are removed during cleanup.
- This is a two-template source slice, not general application discovery,
  containers, browsers, clusters, network access, secret use, or installed
  qualification.

## Alternatives considered

- Let the model provide argv or a recipe coordinate: rejected because model
  output is untrusted data and cannot select executable authority.
- Reuse the protected `.fam/services/api.py` recipe: rejected because ordinary
  natural candidate operations cannot create or change that path.
- Accept an arbitrary candidate service manifest: deferred until a versioned
  contract can map a small declarative vocabulary to installed recipes without
  admitting commands, images, credentials, or authority.
- Infer common framework launch commands: rejected because repository text and
  dependency metadata are not trusted executable policy.

## Evidence

- `src/fam_os/adapters/integration/natural_planning.py`
- `src/fam_os/product/natural_engineering_integration.py`
- `src/fam_os/product/release_assembly.py`
- `tests/unit/test_natural_integration_environment.py`
- `tests/integration/test_natural_integration_environment.py`
- `tests/integration/test_natural_multi_service_process.py`
- `tests/unit/test_release_bundle.py`
