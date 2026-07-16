# Handoff 0007: Python verifier and Bubblewrap sandbox

**Date:** 2026-07-16  
**Plan step:** Phase 1.8  
**Status:** Complete  
**Previous handoff:** `0006-systemd-cgroup-supervisor-adapters.md`

## Objective

Move the parent prototype's deterministic Python verification behind trusted verification contracts and an explicit sandbox port while preserving extraction, sanitation, stable-toposort pass/fail behavior, resource limits, and bounded evidence without copying its verifier god module or silently downgrading isolation.

## Scope completed

- Added provider-neutral `VerificationRequest -> VerificationReport` and `Verifier` interfaces.
- Added typed verification evidence containing bounded stdout, stderr, exit code, normalized candidate, and actual isolation level.
- Added provider-neutral sandbox status, isolation, limits, request, result, and runner contracts.
- Split Python verification into candidate extraction, AST policy, trusted test bundles, script assembly, and verdict conversion modules.
- Kept trusted test bundles inside the configured verifier so Core orchestration cannot receive or replace them.
- Preserved the prototype's Python fence extraction, allowed imports, top-level example removal, deterministic tests, resource limits, and pass-sentinel requirement.
- Added explicit candidate-failure, verifier-error, test-failure, timeout, and pass mappings.
- Added a Bubblewrap adapter with pure command construction, injectable executable discovery, injectable process launch, fixed minimal environment, Python isolated mode, Linux resource limits, returned-output truncation, and wall timeout.
- Required Bubblewrap by default. Process-limit-only execution must be enabled explicitly and reports weaker isolation.
- Closed direct `__builtins__`, dynamic dunder `getattr`, and nested-decorator policy bypasses found during migration.
- Added a FAM-owned trusted stable-toposort fixture.
- Added 20 focused tests, increasing the FAM_OS unit suite from 57 to 77 tests.
- Proved live parity against the parent verifier for one passing and one failing candidate.
- Exercised live Bubblewrap filesystem isolation, timeout termination, and returned-output bounds.

## Explicitly not completed

- No verifier manifest, signature, package trust level, or external report schema was added; those remain Phase 2 and Phase 8 work.
- No seccomp policy, cgroup PID or I/O limit, streaming output enforcement, multi-user isolation, or hostile multi-tenant security claim was added.
- No JavaScript, Rust, mathematics, retrieval, or application-action verifier was added.
- No repair, escalation, attempt budget, prompt, release use case, or orchestration was added; Phase 1.9 is next.
- No report persistence or JSON writer was migrated; serialization belongs outside verifier mechanics.
- The parent `rnf/verifier.py` and its tests were not modified.
- The AST policy is not claimed to be a complete proof against every Python escape technique.

## Architecture and decisions

ADR 0007 establishes four boundaries:

1. `verification/contracts.py` and `verification/ports.py` define provider-neutral requests, reports, evidence, and the verifier port.
2. `verification/sandbox` defines provider-neutral execution limits, isolation levels, outcomes, and the sandbox port.
3. `verification/python` owns trusted Python candidate and acceptance policy.
4. `adapters/bubblewrap` owns Linux process discovery, Bubblewrap arguments, rlimits, and subprocess execution.

`PythonVerifier` is configured with `TrustedPythonTests` and a `SandboxRunner`. Its public `verify()` method accepts only a `VerificationRequest`, preventing orchestration or candidate content from replacing verifier tests.

Candidate syntax or policy rejection, deterministic assertion failure, and timeout produce `VerificationStatus.FAILED`. Missing required Bubblewrap isolation produces `VerificationStatus.ERROR`. Only a completed exit code of zero plus the verifier-owned sentinel produces `VerificationStatus.PASSED`.

Bubblewrap is required by default. The optional process-limit fallback is an explicit compatibility mechanism and returns `IsolationLevel.PROCESS_LIMITS`; it is never represented as equivalent isolation.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/verification/contracts.py` | Verification request, evidence, report, and status contracts |
| `src/fam_os/verification/ports.py` | Provider-neutral verifier port |
| `src/fam_os/verification/sandbox/contracts.py` | Sandbox limits, requests, outcomes, and isolation contracts |
| `src/fam_os/verification/sandbox/ports.py` | Sandbox runner port |
| `src/fam_os/verification/python/extraction.py` | Syntactically valid Markdown/Python extraction |
| `src/fam_os/verification/python/policy.py` | Trusted AST allow policy and top-level sanitation |
| `src/fam_os/verification/python/bundles.py` | Trusted deterministic Python test bundles |
| `src/fam_os/verification/python/script.py` | Candidate, tests, and pass-sentinel assembly |
| `src/fam_os/verification/python/verifier.py` | Validation, sandbox execution, and report conversion |
| `src/fam_os/verification/python/__init__.py`, `README.md` | Python verifier exports and ownership |
| `src/fam_os/verification/__init__.py`, `README.md` | Public verification exports and current boundary |
| `src/fam_os/adapters/bubblewrap/settings.py` | Executables, binds, environment, and downgrade policy |
| `src/fam_os/adapters/bubblewrap/discovery.py` | Injectable executable discovery |
| `src/fam_os/adapters/bubblewrap/commands.py` | Pure isolated/direct Python command construction |
| `src/fam_os/adapters/bubblewrap/rlimits.py` | Child process resource limits |
| `src/fam_os/adapters/bubblewrap/process.py` | Bounded subprocess execution and output conversion |
| `src/fam_os/adapters/bubblewrap/runner.py` | Sandbox port implementation and isolation selection |
| `src/fam_os/adapters/bubblewrap/__init__.py`, `README.md` | Adapter exports and ownership |
| `tests/fixtures/verification/stable_topological_sort_tests.py` | FAM-owned trusted acceptance fixture |
| `tests/unit/test_python_candidate_policy.py` | Parent parity plus AST bypass regressions |
| `tests/unit/test_trusted_python_tests.py` | Trusted bundle construction and validation |
| `tests/unit/test_python_verifier.py` | Fake sandbox verdict and evidence mapping |
| `tests/unit/test_bubblewrap_commands.py` | Exact sandbox command tests |
| `tests/unit/test_bubblewrap_runner.py` | Isolation selection and downgrade tests |
| `tests/unit/test_verification_contracts.py` | Verification request validation |
| `tests/hardware/python_verifier_parity.py` | Parent-versus-FAM live pass/fail parity |
| `tests/hardware/python_sandbox_smoke.py` | Live isolation, timeout, and output checks |
| `docs/decisions/0007-python-verifier-and-sandbox-boundary.md` | Trust and isolation boundary ADR |
| `README.md`, `MASTER_PLAN.md`, component READMEs | Status, evidence, ownership, and next step |

## Public interfaces

- `VerificationRequest`
- `VerificationEvidence`
- `VerificationReport`
- `VerificationReport.failure_details(maximum_characters)`
- `VerificationStatus`
- `Verifier`
- `SandboxStatus`
- `IsolationLevel`
- `SandboxLimits`
- `SandboxRequest`
- `SandboxResult`
- `SandboxRunner`
- `TrustedPythonTests`
- `load_trusted_python_tests(path, bundle_id)`
- `extract_python_candidate(content)`
- `sanitize_python_candidate(code)`
- `PythonVerifier`
- `PYTHON_VERIFIER_ID`
- `BubblewrapSettings`
- `BubblewrapSandboxRunner`

These are source-level Python interfaces. The `TrustedPythonTests` name represents an authority boundary selected by trusted composition code; Phase 8 must add manifest signatures and package trust enforcement.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 77 tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
FAM_VERIFIER_PARITY=1 PYTHONPATH=src:.. python3 -m unittest tests.hardware.python_verifier_parity -v
```

Result: 2 live parity tests passed in 0.049 seconds. Parent and migrated verifiers both accepted the correct implementation and rejected the unstable implementation.

```bash
cd <REPO_ROOT>/FAM_OS
FAM_SANDBOX_SMOKE=1 PYTHONPATH=src python3 -m unittest tests.hardware.python_sandbox_smoke -v
```

Result: 3 live sandbox tests passed in 0.132 seconds. The Bubblewrap root hid `/home`, the infinite loop hit the wall timeout, and returned stdout was exactly the configured 128-character bound.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent RNF tests passed, 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

The codebase knowledge graph was refreshed in fast mode with 1,243 nodes and 4,527 edges. It found the verifier port, verification request, Python verifier, trusted bundle, sandbox port, Bubblewrap runner, AST sanitation function, and process launcher. Graph-augmented search found no parent `rnf` import under `FAM_OS/src/`; subprocess, executable discovery, resource limits, and Bubblewrap strings remain in adapter code.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 194 files indexed, 35 artifacts written, verification clean.

No implementation file exceeds 149 lines. All implementation functions remain below the 50-line target.

## Evidence and artifacts

The live verifier used Bubblewrap 0.9.0 and `/usr/bin/python3`. The parity fixture covers stable branch order, neighbor-only nodes, simultaneous-root order, disconnected-node order, and cycle rejection.

The live sandbox checks recorded only pass/fail behavior and non-sensitive isolation facts. They wrote no artifact and exposed no host home path inside the sandbox.

## Known limitations and risks

- The AST allow policy is a defense layer, not a complete Python security proof.
- Bubblewrap depends on Linux user namespaces and host kernel security.
- No seccomp filter is applied yet.
- Parent-side `subprocess.run(capture_output=True)` accumulates pipe output before returned evidence is truncated. A hardened launcher must enforce streaming output ceilings.
- Address-space rlimits can behave differently across Python and native-library builds.
- Trusted bundles are syntax-validated but not signed, version-schema validated, or tied to package trust metadata.
- The optional process-limit fallback does not isolate filesystem or networking and must remain explicit.
- The current sandbox does not apply cgroup PID, I/O, or service-wide limits.
- Failure evidence can contain candidate-produced text and must remain untrusted when used in future repair prompts.
- Only deterministic Python tests are supported.

## Operational notes

Live validation created only short-lived Bubblewrap/Python child processes. One infinite-loop child was terminated by the 0.1-second wall timeout. No service, model, package, network endpoint, persistent file, device permission, or system configuration was changed.

## Recommended next entry point

Begin Phase 1.9. Map the parent `run_verified_task`, prompt builders, verification feedback, unload calls, and status transitions. Implement fake-driven route, candidate attempt, verify, bounded repair, escalation, and release use cases over `InferenceRuntime` and `Verifier`. Keep scheduler decisions injectable, preserve all failed attempts as evidence, and construct a successful `TaskResult` only from a passing `VerificationReport`.
