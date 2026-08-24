"""Create clean environments that install only the selected built artifact."""

from __future__ import annotations

import json
import os
import subprocess
import venv
from pathlib import Path

from .contracts import ReleaseProfile


def clean_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if base is None else base)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def create_profile_environment(
    *, profile: ReleaseProfile, wheel: Path, root: Path, log_path: Path,
    dependency_wheelhouse: Path | None = None,
) -> tuple[Path, dict[str, object]]:
    venv.EnvBuilder(with_pip=True, clear=False).create(root)
    python = root / "bin/python"
    install_target = f"{wheel}{profile.install_suffix}"
    command = [str(python), "-m", "pip", "install"]
    if dependency_wheelhouse is not None:
        command.extend((
            "--no-index", "--find-links", str(dependency_wheelhouse),
        ))
    command.append(install_target)
    environment = clean_environment()
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run(
            command, check=True, stdout=log, stderr=subprocess.STDOUT,
            text=True, env=environment, timeout=3_600,
        )
    proof = _installation_proof(
        python, profile.distributions, environment, root,
    )
    proof["dependency_mode"] = (
        "offline_wheelhouse" if dependency_wheelhouse is not None else "pip_index"
    )
    return python, proof


def _installation_proof(
    python: Path, distributions: tuple[str, ...], environment: dict[str, str],
    root: Path,
) -> dict[str, object]:
    program = (
        "import importlib.metadata as m,json,pathlib,sys; import fam_os; "
        "p=pathlib.Path(fam_os.__file__).resolve(); "
        "print(json.dumps({'module_path':str(p),'python':sys.version," 
        "'distributions':{n:m.version(n) for n in sys.argv[1:]}}))"
    )
    completed = subprocess.run(
        (str(python), "-c", program, *distributions), check=True,
        capture_output=True, text=True, env=environment, timeout=120,
    )
    proof = json.loads(completed.stdout)
    module_path = Path(proof["module_path"])
    if not module_path.is_relative_to(root.resolve()):
        raise RuntimeError("profile imported FAM_OS outside its clean environment")
    frozen = subprocess.run(
        (str(python), "-m", "pip", "freeze", "--all"), check=True,
        capture_output=True, text=True, env=environment, timeout=120,
    ).stdout.splitlines()
    proof["installed_distributions"] = tuple(sorted(frozen, key=str.casefold))
    return proof
