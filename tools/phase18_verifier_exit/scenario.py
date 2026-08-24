"""Exercise every bound verifier through a signed installed Console and Core."""

from __future__ import annotations

import hashlib
import json

from tools.phase19_exit.console_client import ConsoleClient


def run_scenario(service, release_id: str, signer_key_id: str) -> dict:
    image = service.root / "ocr.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nFAM_OS")
    image_digest = hashlib.sha256(image.read_bytes()).hexdigest()
    client = ConsoleClient(
        f"http://127.0.0.1:{service.port}",
        (service.runtime_root / "console.token").read_text().strip(),
    )
    tasks = (
        ("signed-exact", "Return READY", {
            "kind": "exact_text", "expected_text": "READY",
        }),
        ("signed-python", "Write Python code for add", {
            "kind": "python_tests", "bundle_id": "add-v1",
            "test_source": "assert add(2, 3) == 5\nassert add(-1, 1) == 0",
        }),
        ("signed-retrieval", "Search the supplied source", {
            "kind": "retrieval_citations", "sources": [{
                "source_id": "source-1", "locator": "memory://source-1",
                "content": "FAM_OS runs locally.", "provenance_id": "phase18-exit",
            }],
        }),
        ("signed-math", "Calculate the equation", {
            "kind": "math_equivalence", "reference_expression": "(x+1)**2",
            "variable": "x", "sample_points": ["-2", "0", "3.5"],
            "absolute_tolerance": "1e-40", "precision_digits": 50,
        }),
        ("signed-media", "OCR this image", {
            "kind": "media_artifact_text", "artifact_path": str(image),
            "artifact_sha256": image_digest, "expected_text": "FAM_OS",
            "maximum_artifact_bytes": 1024,
        }),
    )
    results = []
    for request_id, prompt, verification in tasks:
        accepted = client.create_verified(request_id, prompt, verification)
        terminal = client.wait_for_terminal(accepted["session_id"])
        runs = client.verifications(accepted["session_id"])
        if terminal["result"]["status"] != "verified" or not runs:
            raise RuntimeError(
                f"installed verifier task failed: terminal={terminal}; runs={runs}"
            )
        if any(
            item["effective_trust"] != "signed"
            or item["release_id"] != release_id
            or item["signer_key_id"] != signer_key_id
            for item in runs
        ):
            raise RuntimeError("installed verifier did not retain signed binding evidence")
        results.append({
            "request_id": request_id,
            "session_id": accepted["session_id"],
            "status": terminal["result"]["status"],
            "evidence_ids": terminal["result"]["evidence_ids"],
            "runs": runs,
        })
    return {"tasks": results, "image_sha256": image_digest}


def scripted_responses() -> tuple[str, ...]:
    return (
        "READY",
        "def add(left, right):\n    return left + right\n",
        json.dumps({
            "answer": "FAM_OS runs locally.",
            "claims": [{
                "text": "FAM_OS runs locally.", "source_id": "source-1",
                "quote": "FAM_OS runs locally.",
            }],
        }),
        json.dumps({"expression": "x**2 + 2*x + 1"}),
        "",  # replaced after the media artifact digest is known
    )


def media_response(image_sha256: str) -> str:
    return json.dumps({
        "artifact_sha256": image_sha256, "observed_text": "FAM_OS",
    })
