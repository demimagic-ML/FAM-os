"""Small offline worker that invokes two pinned llama.cpp converters."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


_BASE_TYPES = frozenset(("f16", "bf16", "q8_0"))
_ADAPTER_TYPES = frozenset(("f16", "bf16"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    arguments = parser.parse_args(argv)
    return _convert(arguments.config, Path("/output"))


def _convert(config_path: Path, output: Path) -> int:
    base = output / "base.gguf"
    adapter = output / "adapter.gguf"
    modelfile = output / "Modelfile"
    result = output / "worker-result.json"
    try:
        config = _config(config_path)
        base_type = _choice(config, "base_output_type", _BASE_TYPES)
        adapter_type = _choice(config, "adapter_output_type", _ADAPTER_TYPES)
        maximum = _positive_integer(config, "maximum_output_bytes")
        runtime_ref = _text(config, "runtime_model_ref")
        _run((
            "/environment/bin/python", "/llama.cpp/convert_hf_to_gguf.py",
            "/model", "--outfile", str(base), "--outtype", base_type,
        ))
        _require_output(base)
        _require_size(output, maximum)
        _run((
            "/environment/bin/python", "/llama.cpp/convert_lora_to_gguf.py",
            "/adapter", "--base", "/model", "--outfile", str(adapter),
            "--outtype", adapter_type,
        ))
        _require_output(adapter)
        modelfile.write_text(
            "FROM ./base.gguf\nADAPTER ./adapter.gguf\nPARAMETER temperature 0\n",
            encoding="utf-8",
        )
        os.chmod(modelfile, 0o600)
        _require_size(output, maximum)
        document = {
            "adapter_gguf_bytes": adapter.stat().st_size,
            "adapter_gguf_sha256": _sha(adapter),
            "base_gguf_bytes": base.stat().st_size,
            "base_gguf_sha256": _sha(base),
            "modelfile_sha256": _sha(modelfile),
            "reason_code": "conversion.completed",
            "runtime_model_ref": runtime_ref,
            "status": "completed",
        }
        _write_result(result, document)
        _require_size(output, maximum)
        return 0
    except Exception:
        for path in (base, adapter, modelfile):
            path.unlink(missing_ok=True)
        _write_result(result, {
            "reason_code": "conversion.worker_failed", "status": "failed",
        })
        return 1


def _config(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("conversion config is invalid")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("conversion config is invalid")
    return value


def _run(command: tuple[str, ...]) -> None:
    subprocess.run(command, check=True, timeout=None)


def _require_output(path: Path) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size < 1:
        raise RuntimeError("conversion output is invalid")


def _require_size(root: Path, maximum: int) -> None:
    if sum(item.stat().st_size for item in root.iterdir() if item.is_file()) > maximum:
        raise RuntimeError("conversion output exceeded approval")


def _choice(
    config: dict[str, object], name: str, allowed: frozenset[str],
) -> str:
    value = _text(config, name)
    if value not in allowed:
        raise ValueError("conversion output type is invalid")
    return value


def _text(config: dict[str, object], name: str) -> str:
    value = config.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"conversion {name} is invalid")
    return value


def _positive_integer(config: dict[str, object], name: str) -> int:
    value = config.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"conversion {name} is invalid")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_result(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
