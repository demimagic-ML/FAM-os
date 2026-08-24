# Clean test and dependency profiles

FAM_OS keeps the always-installed runtime small and declares optional capability
profiles explicitly. Tests must skip only when their declared profile or required
physical hardware is absent; missing undeclared Python packages are failures.

| Profile | Install selector | Purpose | Expected environment skips |
|---|---|---|---|
| Base | `.` | Core contracts, service, Shell, Console, CPU-safe adapters | GPU, physical peer, external app |
| Verification | `.[verification]` | Python quality verifiers | none |
| Mathematics | `.[mathematics]` | SymPy-backed deterministic math | none |
| Media | `.[media]` | Speech, image, OCR-capable paths | unavailable media devices/models |
| Development | `.[development]` | lint, typing, build, coverage tools | hardware integration only |
| Hardware | `.[hardware]` | NVIDIA and host telemetry | unavailable accelerator types |
| Training | `.[training]` | PyTorch/TRL/PEFT/bitsandbytes factory | CUDA training without supported GPU |

## Canonical clean-artifact command

Run one profile with the Phase 23 matrix tool:

```bash
.verification-venv/bin/python -m tools.run_phase23_release_matrix \
  --profile PROFILE \
  --run-id phase23-PROFILE-YYYYMMDD-NN
```

Omit `--profile` to run every Master Plan-required profile from one newly built
wheel. The tool creates an isolated venv per profile, removes `PYTHONPATH` and
`PYTHONHOME`, proves `fam_os` resolves inside that venv, records the installed
distribution set, runs all standard tests, and validates every skip against the
declared environment boundary. An optional `--dependency-wheelhouse` makes pip
installation offline and fail-closed.

The Hardware profile separately discovers `tests/hardware/*_smoke.py`; the two
Phase 1 parent-prototype parity comparators are reproduction tools and are not
part of a shipped-artifact test suite. The VS Code profile performs a clean
`npm ci`, compiles and tests the connector, runs cross-language transport and
schema checks with the wheel interpreter, builds a deterministic VSIX, and
proves isolated VS Code install/list/removal.

Canonical consolidated evidence is
`artifacts/product/phase23/profile-matrix/phase23-required-20260718-01/profile-matrix.json`.
A passing source-tree environment is not a substitute for this release-artifact
matrix. Declared physical skips in the clean Hardware profile also do not
substitute for Phase 23.4's independent CPU-only and full-workstation runs.
