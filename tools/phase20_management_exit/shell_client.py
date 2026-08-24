"""Invoke the installed FAM Shell terminal against the installed service."""

import subprocess


def run_installed_shell(installation, service, commands: tuple[str, ...]) -> dict:
    process = subprocess.run(
        (
            str(installation.prefix / "bin/fam-shell"),
            "--socket", str(service.runtime_root / "shell.sock"),
            "--timeout", "20",
        ),
        input="\n".join((*commands, "/quit")) + "\n",
        capture_output=True, text=True, timeout=120, check=False,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
