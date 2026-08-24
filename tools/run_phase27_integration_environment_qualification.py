#!/usr/bin/python3
"""Sign, install, and run Docker/process plus owner-lifecycle scenarios."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


PROFILES = ("compat-cpu-16gb", "full-reference-workstation")
SCENARIOS = (
    "tests.unit.test_installed_integration_recipes",
    "tests.integration.test_process_api_integration_environment",
    "tests.unit.test_process_integration_environment",
    "tests.unit.test_process_environment_state",
    "tests.unit.test_engineering_secret_repository",
    "tests.unit.test_engineering_secret_api",
    "tests.unit.test_integration_retained_artifacts",
    "tests.integration.test_docker_integration_environment",
    "tests.unit.test_integration_environment_repository",
    "tests.unit.test_integration_environment_service",
    "tests.unit.test_production_database",
    "tests.unit.test_product_integration_environment_api",
    "tests.integration.test_console_integration_environments",
    "tests.integration.test_console_engineering_secrets",
    "tests.unit.test_fam_shell_integration_environment_transport",
    "tests.unit.test_fam_shell_engineering_secret_transport",
    "tests.unit.test_integration_environment_router",
    "tests.unit.test_mixed_integration_environment",
    "tests.integration.test_real_mixed_integration_environment",
    "tests.integration.test_installed_process_owner_restart_chain",
    "tests.unit.test_bounded_devtools_client",
    "tests.integration.test_real_browser_integration_environment",
    "tests.unit.test_integration_network_authority",
    "tests.unit.test_integration_network_broker",
    "tests.unit.test_integration_network_broker_handler",
    "tests.unit.test_integration_network_broker_server",
    "tests.unit.test_integration_network_broker_service",
    "tests.unit.test_integration_network_supervisor_authorizer",
    "tests.unit.test_linux_namespace_network_enforcement",
    "tests.unit.test_docker_network_enforcement",
    "tests.unit.test_multi_network_enforcement",
    "tests.unit.test_supervisor_network_enforcement",
    "tests.unit.test_supervisor_network_proxy",
    "tests.unit.test_supervisor_network_proxy_runtime",
    "tests.unit.test_product_integration_network_composition",
    "tests.unit.test_product_network_authority_export",
    "tests.unit.test_network_broker_root_entrypoint",
    "tests.unit.test_signed_bundle_installation",
    "tests.unit.test_installation_marker",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--builder-python", type=Path, required=True)
    return _qualify(parser.parse_args())


def _qualify(args) -> int:
    repository = args.repository.resolve()
    builder = args.builder_python.resolve()
    started = time.monotonic()
    release_id = "phase27-network-source-package-20260719-attempt16"
    with tempfile.TemporaryDirectory(prefix="fam-phase27-integration-") as raw:
        root = Path(raw)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        build = _run((
            str(builder), "-m", "pip", "wheel", str(repository), "--no-deps",
            "--wheel-dir", str(wheelhouse),
        ), repository, 600)
        wheels = tuple(wheelhouse.glob("fam_os-*.whl"))
        if build.returncode or len(wheels) != 1:
            return _write(args.output, release_id, started, None, None, (), build)
        wheel = wheels[0]
        public, signature = _sign(wheel)
        environment = root / "installed"
        create = _run((
            str(builder), "-m", "venv", "--system-site-packages", str(environment),
        ), root, 120)
        if create.returncode:
            return _write(args.output, release_id, started, wheel, (public, signature), (), create)
        python = environment / "bin/python"
        install = _run((
            str(python), "-m", "pip", "install", "--no-deps", str(wheel),
        ), root, 180)
        if install.returncode:
            return _write(args.output, release_id, started, wheel, (public, signature), (), install)
        purelib = _run((
            str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))",
        ), root, 10, _environment())
        if purelib.returncode:
            return _write(args.output, release_id, started, wheel, (public, signature), (), purelib)
        test_target = Path(purelib.stdout.strip()) / "tests"
        shutil.copytree(repository / "tests", test_target)
        identity = _run((
            str(python), "-c", "import fam_os; print(fam_os.__file__)",
        ), root, 10, _environment())
        runs = []
        for profile in PROFILES:
            values = _environment()
            values["FAM_ENGINEERING_HARDWARE_PROFILE"] = profile
            runs.append((profile, _run(
                (str(python), "-m", "unittest", "-v", *SCENARIOS),
                root, 300, values,
            )))
        return _write(
            args.output, release_id, started, wheel, (public, signature),
            tuple(runs), identity,
        )


def _environment():
    values = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1",
    }
    for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        if name in os.environ:
            values[name] = os.environ[name]
    return values


def _run(command, cwd, timeout, environment=None):
    return subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True,
        timeout=timeout,
    )


def _sign(wheel):
    content = wheel.read_bytes()
    private = Ed25519PrivateKey.generate()
    signature = private.sign(content)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    private.public_key().verify(signature, content)
    return public, signature


def _write(path, release_id, started, wheel, signing, runs, setup):
    passed = bool(
        wheel and signing and setup.returncode == 0
        and len(runs) == len(PROFILES)
        and all(result.returncode == 0 for _profile, result in runs)
        and "site-packages/fam_os/__init__.py" in setup.stdout
    )
    document = {
        "schema_id": "fam.engineering.integration-environment-installed-qualification/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "release_id": release_id,
        "passed": passed,
        "allowlisted_egress_enforcement": "source_contract_only",
        "installed_root_broker_exercised": False,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "wheel_sha256": None if not wheel else hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "signer_public_key_sha256": None if not signing else hashlib.sha256(signing[0]).hexdigest(),
        "signature_base64": None if not signing else base64.b64encode(signing[1]).decode(),
        "installed_module": setup.stdout.strip(),
        "physical_observation": _physical_observation(),
        "profiles": {
            profile: {
                "passed": result.returncode == 0,
                "exit_code": result.returncode,
                "output_sha256": hashlib.sha256(
                    (result.stdout + result.stderr).encode()
                ).hexdigest(),
                "tail": (result.stdout + result.stderr)[-4096:],
            }
            for profile, result in runs
        },
        "setup_stderr": setup.stderr[-4096:],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    print(path)
    return 0 if passed else 1


def _physical_observation():
    memory = next(
        int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemTotal:")
    )
    return {
        "machine": platform.machine(), "kernel": platform.release(),
        "logical_cpus": os.cpu_count(), "host_memory_kib": memory,
    }


if __name__ == "__main__":
    raise SystemExit(main())
