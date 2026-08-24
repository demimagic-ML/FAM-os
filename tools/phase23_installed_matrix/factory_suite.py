"""Build the immutable canary input used by installed Factory qualification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def materialize_canary_suite(
    *, prompt_configuration: Path, verifier_tests: Path, target: Path,
) -> dict[str, object]:
    configuration = json.loads(prompt_configuration.read_text("utf-8"))
    prompt = configuration.get("prompt") if isinstance(configuration, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("canary prompt configuration is invalid")
    test_source = verifier_tests.read_text("utf-8")
    if not test_source.strip():
        raise ValueError("canary verifier tests are empty")
    document = {
        "bundle_id": "stable-toposort-v2",
        "case_id": "stable-toposort-production-contract",
        "prompt": prompt,
        "test_source": test_source,
    }
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(target.parent, 0o700)
    descriptor = os.open(
        target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "case_count": 1,
        "prompt_configuration_sha256": _sha(prompt_configuration),
        "suite_sha256": hashlib.sha256(payload).hexdigest(),
        "verifier_tests_sha256": _sha(verifier_tests),
    }


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
