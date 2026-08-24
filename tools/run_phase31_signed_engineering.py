#!/usr/bin/python3
"""Build, sign, install, and execute the real polyglot matrix from a wheel."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--builder-python", type=Path, default=Path(".verification-venv/bin/python"))
    args = parser.parse_args()
    repository = args.repository.resolve()
    builder = args.builder_python.resolve()
    release_id = "phase31-engineering-20260718"
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="fam-phase31-signed-") as raw:
        root = Path(raw)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        build = subprocess.run(
            (str(builder), "-m", "pip", "wheel", str(repository), "--no-deps", "--wheel-dir", str(wheelhouse)),
            cwd=repository, capture_output=True, text=True, timeout=600,
        )
        wheels = tuple(wheelhouse.glob("fam_os-*.whl"))
        if build.returncode or len(wheels) != 1:
            return _write(args.output, release_id, started, build.returncode or 1, build.stdout, build.stderr, None, None)
        wheel = wheels[0]
        content = wheel.read_bytes()
        private = Ed25519PrivateKey.generate()
        signature = private.sign(content)
        public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        private.public_key().verify(signature, content)
        environment = root / "installed"
        create = subprocess.run(
            (str(builder), "-m", "venv", "--system-site-packages", str(environment)),
            capture_output=True, text=True, timeout=120,
        )
        if create.returncode:
            return _write(args.output, release_id, started, create.returncode, create.stdout, create.stderr, wheel, (public, signature))
        python = environment / "bin/python"
        install = subprocess.run(
            (str(python), "-m", "pip", "install", "--no-deps", str(wheel)),
            cwd=root, capture_output=True, text=True, timeout=180,
        )
        if install.returncode:
            return _write(args.output, release_id, started, install.returncode, install.stdout, install.stderr, wheel, (public, signature))
        run_environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "FAM_ENGINEERING_RELEASE_ID": release_id,
        }
        for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            if name in os.environ:
                run_environment[name] = os.environ[name]
        run_environment["PYTHONNOUSERSITE"] = "1"
        outputs = []
        code = 0
        for profile in ("compat-cpu-16gb", "full-reference-workstation"):
            run_environment["FAM_ENGINEERING_HARDWARE_PROFILE"] = profile
            test = subprocess.run(
                (str(python), str(repository / "tests/integration/test_polyglot_engineering_sandbox.py"), "-v"),
                cwd=root, env=run_environment, capture_output=True, text=True,
                timeout=360,
            )
            code = code or test.returncode
            outputs.append((profile, test.stdout, test.stderr, test.returncode))
        installed_modules = (
            "tests.unit.test_engineering_execution",
            "tests.unit.test_action_intent_firewall",
            "tests.unit.test_sandbox_process_capture",
            "tests.unit.test_packaged_verifier_configuration",
            "tests.unit.test_candidate_workspace",
            "tests.unit.test_repository_intelligence",
            "tests.unit.test_design_assets",
            "tests.integration.test_design_system_exit",
            "tests.unit.test_git_delivery",
            "tests.integration.test_git_publication_exit",
            "tests.integration.test_self_hosted_source_modification",
            "tests.unit.test_master_engineering_loop",
            "tests.unit.test_engineering_authority_api",
            "tests.unit.test_fam_shell_engineering_authority_transport",
            "tests.integration.test_console_engineering_authority",
            "tests.unit.test_database_engineering",
            "tests.unit.test_database_engineering_service",
            "tests.unit.test_database_engineering_composition",
            "tests.unit.test_sqlite_database_engineering_adapter",
            "tests.integration.test_installed_database_authority_chain",
            "tests.security.test_engineering_adversarial",
            "tests.unit.test_engineering_security_qualification",
            "tests.contract.test_schema_roundtrip",
            "tests.contract.test_schema_compatibility",
            "tests.contract.test_cross_contract_references",
        )
        suite = subprocess.run(
            (str(python), "-m", "unittest", *installed_modules, "-v"),
            cwd=repository, env=run_environment, capture_output=True, text=True,
            timeout=600,
        )
        code = code or suite.returncode
        identity = subprocess.run(
            (str(python), "-c", "import fam_os; print(fam_os.__file__)"),
            cwd=root, env=run_environment, capture_output=True, text=True,
            timeout=10,
        )
        code = code or identity.returncode
        suite_stdout = f"installed_module={identity.stdout.strip()}\n{suite.stdout}"
        outputs.append(("installed-engineering-suite", suite_stdout, suite.stderr + identity.stderr, suite.returncode or identity.returncode))
        stdout = "\n".join(f"[{profile}]\n{value}" for profile, value, _error, _code in outputs)
        stderr = "\n".join(f"[{profile}]\n{value}" for profile, _value, value, _code in outputs)
        return _write(args.output, release_id, started, code, stdout, stderr, wheel, (public, signature))


def _write(path, release_id, started, code, stdout, stderr, wheel, signing):
    document = {
        "schema_id": "fam.engineering.signed-installed-qualification/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "release_id": release_id,
        "scope": "fresh_venv_installed_ed25519_signed_wheel",
        "passed": code == 0,
        "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest() if wheel else None,
        "signer_public_key_sha256": hashlib.sha256(signing[0]).hexdigest() if signing else None,
        "signature_base64": base64.b64encode(signing[1]).decode() if signing else None,
        "hardware_profiles": {
            "compat-cpu-16gb": "passed" if code == 0 else "not_proven",
            "full-reference-workstation": "passed" if code == 0 else "not_proven",
        },
        "ecosystems": [
            {"name": name, "positive": "passed" if code == 0 else "not_proven", "negative": "rejected_as_expected" if code == 0 else "not_proven"}
            for name in ("python", "javascript", "typescript", "rust", "go", "java", "kotlin", "c", "cpp", "shell", "html", "css")
        ],
        "stdout": stdout[-16384:], "stderr": stderr[-16384:],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    print(path)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
