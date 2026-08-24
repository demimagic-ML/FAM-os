"""Download one immutable approved Hugging Face base and hash every file."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.destination.exists():
        raise FileExistsError("approved base model destination already exists")
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=arguments.repository, revision=arguments.revision,
        local_dir=arguments.destination, cache_dir=arguments.cache,
    )
    files = []
    for path in sorted(arguments.destination.rglob("*")):
        if path.is_symlink():
            raise ValueError("approved base model cannot contain symlinks")
        if path.is_file():
            files.append({
                "bytes": path.stat().st_size,
                "path": path.relative_to(arguments.destination).as_posix(),
                "sha256": _file_sha256(path),
            })
    if not files:
        raise RuntimeError("approved base model download is empty")
    files_manifest_sha256 = hashlib.sha256(json.dumps(
        tuple((item["path"], item["sha256"]) for item in files),
        separators=(",", ":"),
    ).encode()).hexdigest()
    document = {
        "contract_version": "fam.factory.base-model-files/v1alpha1",
        "files": files, "files_manifest_sha256": files_manifest_sha256,
        "license_id": arguments.license, "repository_id": arguments.repository,
        "revision": arguments.revision,
    }
    document["manifest_sha256"] = hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    arguments.manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = arguments.manifest.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    temporary.replace(arguments.manifest)
    print(json.dumps({
        "file_count": len(files),
        "files_manifest_sha256": files_manifest_sha256,
        "manifest": str(arguments.manifest),
        "total_bytes": sum(item["bytes"] for item in files),
    }, sort_keys=True))
    return 0


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
