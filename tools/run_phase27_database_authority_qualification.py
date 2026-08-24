#!/usr/bin/python3
"""Build, sign, install, and qualify the database authority chain."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


PROFILES = ("compat-cpu-16gb", "full-reference-workstation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--builder-python", type=Path,
        default=Path(".verification-venv/bin/python"),
    )
    return _qualify(parser.parse_args())


def _qualify(args) -> int:
    repository = args.repository.resolve()
    builder = args.builder_python.resolve()
    started = time.monotonic()
    release_id = "phase27-database-authority-20260719"
    with tempfile.TemporaryDirectory(prefix="fam-phase27-database-") as raw:
        root = Path(raw)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        build = _run((
            str(builder), "-m", "pip", "wheel", str(repository), "--no-deps",
            "--wheel-dir", str(wheelhouse),
        ), repository, 600)
        wheels = tuple(wheelhouse.glob("fam_os-*.whl"))
        if build.returncode or len(wheels) != 1:
            return _write(
                args.output, release_id, started, None, None, (), build,
            )
        wheel = wheels[0]
        public, signature = _sign(wheel)
        environment = root / "installed"
        create = _run((
            str(builder), "-m", "venv", "--system-site-packages", str(environment),
        ), root, 120)
        if create.returncode:
            return _write(
                args.output, release_id, started, wheel, (public, signature), (), create,
            )
        python = environment / "bin/python"
        install = _run((
            str(python), "-m", "pip", "install", "--no-deps", str(wheel),
        ), root, 180)
        if install.returncode:
            return _write(
                args.output, release_id, started, wheel, (public, signature), (), install,
            )
        identity = _run((
            str(python), "-c", "import fam_os; print(fam_os.__file__)",
        ), root, 10, _environment())
        runs = []
        scenario = repository / "tests/integration/test_installed_database_authority_chain.py"
        for profile in PROFILES:
            environment_values = _environment()
            environment_values["FAM_ENGINEERING_HARDWARE_PROFILE"] = profile
            environment_values["PYTHONPATH"] = str(repository)
            result = _run((str(python), str(scenario), "-v"), root, 120, environment_values)
            runs.append((profile, result))
        return _write(
            args.output, release_id, started, wheel, (public, signature),
            tuple(runs), identity,
        )


def _sign(wheel):
    content = wheel.read_bytes()
    private = Ed25519PrivateKey.generate()
    signature = private.sign(content)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    private.public_key().verify(signature, content)
    return public, signature


def _environment():
    values = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
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


def _write(path, release_id, started, wheel, signing, runs, setup):
    passed = bool(
        wheel is not None and signing is not None and setup.returncode == 0
        and len(runs) == len(PROFILES)
        and all(result.returncode == 0 for _profile, result in runs)
        and "site-packages/fam_os/__init__.py" in setup.stdout
    )
    document = {
        "schema_id": "fam.engineering.database-authority-installed-qualification/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "release_id": release_id,
        "passed": passed,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "wheel_sha256": (
            None if wheel is None else hashlib.sha256(wheel.read_bytes()).hexdigest()
        ),
        "signer_public_key_sha256": (
            None if signing is None else hashlib.sha256(signing[0]).hexdigest()
        ),
        "signature_base64": (
            None if signing is None else base64.b64encode(signing[1]).decode()
        ),
        "installed_module": setup.stdout.strip(),
        "physical_observation": _physical_observation(),
        "profiles": {
            profile: {
                "passed": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
                "tail": (result.stdout + result.stderr)[-4096:],
            }
            for profile, result in runs
        },
        "setup_stderr": setup.stderr[-4096:],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(path)
    return 0 if passed else 1


def _physical_observation():
    meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
    memory_kib = next(
        int(line.split()[1]) for line in meminfo.splitlines()
        if line.startswith("MemTotal:")
    )
    cgroup_relative = Path("/")
    for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
        if line.startswith("0::"):
            cgroup_relative = Path(line.removeprefix("0::").lstrip("/"))
            break
    cgroup = Path("/sys/fs/cgroup") / cgroup_relative
    return {
        "machine": platform.machine(),
        "kernel": platform.release(),
        "logical_cpus": os.cpu_count(),
        "host_memory_kib": memory_kib,
        "cgroup_path": "/" + cgroup_relative.as_posix(),
        "cgroup_memory_max": _read_limit(cgroup / "memory.max"),
        "cgroup_cpu_max": _read_limit(cgroup / "cpu.max"),
    }


def _read_limit(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
