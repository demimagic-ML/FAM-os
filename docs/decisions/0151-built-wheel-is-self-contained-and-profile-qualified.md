# ADR 0151: The built wheel is self-contained and profile-qualified

Status: Accepted

## Context

Source-tree tests and signed bundle assembly both supplied configuration outside
the Python wheel. A clean wheel-only Base run exposed that production verifier
declarations and bindings were absent. After that was corrected, the same run
exposed a second omission: the runtime model catalog was absent, so an installed
wheel could not see the embedding tier and silently disabled document indexing.

The documented profile command also set checkout `PYTHONPATH` and discovered
only `test*.py`. It therefore could not prove artifact imports and never loaded
the separately named hardware smoke suite.

## Decision

The wheel includes exact copies of the canonical production verifier documents,
bindings, and runtime model catalog as `fam_os.product.resources` package data.
Signed installed releases retain first precedence and load their signed expert
archive. Source checkouts retain second precedence. Only a wheel lacking both
boundaries uses the packaged local-unverified defaults, and only model entries
with physically present, digest-observed Ollama manifests are admitted.

Phase 23 profile qualification is implemented as small cooperating modules. One
wheel is built per matrix. Each profile receives a new venv with checkout import
overrides removed, exact installed distribution and `fam_os` origin evidence,
the complete standard suite, declared-skip validation, and profile-specific
checks. Hardware additionally discovers `*_smoke.py`; frozen parent-prototype
parity comparators remain reproduction tools. VS Code gets a clean npm tree,
compiled/Node/cross-language tests, deterministic VSIX construction, and an
isolated real VS Code install/list/remove cycle.

## Consequences

- Wheel-only services retain production verifier declarations and embedding
  catalog composition instead of degrading because checkout files are absent.
- Canonical configuration and packaged copies can drift only by failing an
  exact-byte regression.
- Profile evidence proves the product import came from the built wheel, not
  `src/` or a previous install.
- An opt-in hardware skip remains visible and cannot be used as Phase 23.4
  physical evidence.
- The wheel defaults are local-unverified configuration. They do not weaken or
  replace signed-release component verification.
- Phase 23.1–23.2 can be reproduced without one god script; later installed,
  physical, soak, review, and lifecycle gates remain independent.

## Alternatives considered

- Continuing to copy configuration only into signed bundles was rejected
  because the declared clean wheel profile is itself a supported artifact.
- Falling back to one economical model was rejected because it silently removes
  document memory even when the embedding model is present.
- Setting `PYTHONPATH=src:.` was rejected because it proves the checkout rather
  than the wheel.
- Discovering every `tests/hardware/*.py` file was rejected because two frozen
  Phase 1 parity comparators intentionally depend on the parent prototype and
  are not shipped-release hardware tests.
- Combining all profile, installed, soak, and physical work in one runner was
  rejected because it would obscure authority and create a god script.

## Evidence

- `src/fam_os/product/composition/verifier_unit.py`
- `src/fam_os/product/composition/catalog_unit.py`
- `src/fam_os/product/resources/verifiers/`
- `src/fam_os/product/resources/verifier-bindings/`
- `src/fam_os/product/resources/runtime/model-catalog.json`
- `tools/phase23_release_matrix/`
- `tools/run_phase23_release_matrix.py`
- `tests/unit/test_packaged_verifier_configuration.py`
- `tests/unit/test_packaged_runtime_catalog.py`
- `tests/unit/test_phase23_release_matrix.py`
- `artifacts/product/phase23/profile-matrix/phase23-required-20260718-01/profile-matrix.json`
