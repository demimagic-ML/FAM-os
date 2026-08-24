"""Build, test, and install the VS Code connector as a clean artifact."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .artifacts import file_sha256
from .environment import clean_environment


EXTENSION_ID = "fam-os.fam-os-vscode-connector"


def run_vscode_profile(
    *, python: Path, repository: Path, root: Path, output_root: Path, code: Path,
) -> dict[str, object]:
    if not code.is_file() or code.is_symlink():
        raise RuntimeError("VS Code executable is unavailable or unsafe")
    source = repository / "connectors/vscode"
    connector = root / "connector"
    shutil.copytree(
        source, connector,
        ignore=shutil.ignore_patterns("node_modules", "out", "*.vsix"),
    )
    _command(("npm", "ci"), connector, output_root / "npm-ci.log")
    _command(("npm", "run", "compile"), connector, output_root / "compile.log")
    _command(
        ("node", "--test", "out/test"), connector,
        output_root / "node-tests.log",
    )
    _command(
        (str(python), "test/native_transport_integration.py"), connector,
        output_root / "transport-test.log",
    )
    _command(
        (str(python), "test/validate_schemas.py"), connector,
        output_root / "schema-test.log",
    )
    vsix = output_root / "fam-os-vscode-connector.vsix"
    program = (
        "from pathlib import Path; "
        "from fam_os.product.vscode_package import build_vscode_vsix; "
        "import sys; build_vscode_vsix(Path(sys.argv[1]),Path(sys.argv[2]))"
    )
    _command(
        (str(python), "-c", program, str(connector), str(vsix)),
        repository, output_root / "vsix-build.log",
    )
    profile = root / "code-profile"
    extensions = root / "extensions"
    common = (
        str(code), "--user-data-dir", str(profile),
        "--extensions-dir", str(extensions),
    )
    _command(
        (*common, "--install-extension", str(vsix), "--force"), repository,
        output_root / "code-install.log",
    )
    listed = _command(
        (*common, "--list-extensions", "--show-versions"), repository,
        output_root / "code-list.log", capture=True,
    )
    if not any(line.startswith(f"{EXTENSION_ID}@") for line in listed.splitlines()):
        raise RuntimeError("VS Code did not list the installed FAM_OS connector")
    _command(
        (*common, "--uninstall-extension", EXTENSION_ID), repository,
        output_root / "code-uninstall.log",
    )
    after = _command(
        (*common, "--list-extensions", "--show-versions"), repository,
        output_root / "code-list-after-remove.log", capture=True,
    )
    if any(line.startswith(f"{EXTENSION_ID}@") for line in after.splitlines()):
        raise RuntimeError("VS Code connector remained after isolated removal")
    return {
        "extension_id": EXTENSION_ID,
        "isolated_install": True,
        "removed": True,
        "vsix_name": vsix.name,
        "vsix_sha256": file_sha256(vsix),
    }


def _command(
    command: tuple[str, ...], cwd: Path, log_path: Path, *, capture: bool = False,
) -> str:
    environment = clean_environment()
    if capture:
        completed = subprocess.run(
            command, cwd=cwd, env=environment, check=True,
            capture_output=True, text=True, timeout=600,
        )
        log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        return completed.stdout
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run(
            command, cwd=cwd, env=environment, check=True,
            stdout=log, stderr=subprocess.STDOUT, text=True, timeout=600,
        )
    return ""
