"""Complete signed-install Phase 19 workstation scenario."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from tools.phase19_exit.console_client import ConsoleClient
from tools.phase19_exit.release_environment import (
    InstalledService,
    build_and_install,
    configure_project,
)
from tools.phase19_exit.vscode_process import InstalledVsCodeProcess


def run(repository: Path, code_path: Path, ollama_url: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="fam-phase19-") as raw:
        root = Path(raw)
        project = _project(root)
        state = root / "state"
        configure_project(state, project)
        installation, manifest, connector, extensions = build_and_install(
            repository, root,
        )
        service = InstalledService(installation, root, ollama_url)
        try:
            with service:
                token = (service.runtime_root / "console.token").read_text().strip()
                console = ConsoleClient(
                    f"http://127.0.0.1:{service.port}", token,
                )
                with InstalledVsCodeProcess(
                    code_path, root / "vscode-profile", extensions,
                    service.runtime_root / "applications.sock",
                ) as vscode:
                    target = project / "active.py"
                    vscode.start(project, target)
                    vscode_context = console.wait_for_context(
                        "vscode.workspace_edit.apply", 45,
                    )
                    results = _run_tasks(console, project, target, vscode_context)
        finally:
            if service._process.poll() is None:
                service.stop()
        diagnosis = installation.diagnose()
        installation.remove()
        results.update({
            "release_id": manifest.release_id,
            "release_component_count": len(manifest.components),
            "signed_install_healthy": diagnosis.healthy,
            "connector_version": connector.version,
            "connector_source_digest": connector.source_digest,
            "complete_removal": not installation.prefix.exists(),
        })
        results["passed"] = all((
            results["signed_install_healthy"], results["complete_removal"],
            results["summary_grounded"], results["test_verified"],
            results["edit_previewed"], results["edit_verified"],
            results["undo_verified"], results["reversal_token_private"],
        ))
        return results


def _run_tasks(console, project: Path, target: Path, vscode_context: dict) -> dict:
    project_context = _context(
        "project", "application", "project-phase19", "Phase 19 project",
        ["os.file.read", "project.test"],
    )
    readme = project / "README.md"
    summary = console.create(
        "phase19-summary", "Summarize this project README using only observed content.",
        [project_context, _context(
            "readme", "file", readme.as_uri(), "README.md", [],
        )], ["os.file.read"], True,
    )
    summary = console.wait_for_terminal(summary["session_id"])

    test = console.create(
        "phase19-test", "Run the owner-approved project tests.",
        [project_context], ["project.test"], True,
    )
    test = console.wait_for_approval(test["session_id"])
    console.approve(test)
    test = console.wait_for_terminal(test["session_id"])

    edit_parameters = _edit_parameters(target)
    edit = console.create(
        "phase19-edit",
        "Replace the first line exactly as specified. Return only this JSON: "
        + json.dumps(edit_parameters, separators=(",", ":")),
        [_console_context(vscode_context), _context(
            "active-file", "file", target.as_uri(), "active.py", [],
        )], ["vscode.editor.active", "vscode.workspace_edit.apply"], True,
    )
    edit = console.wait_for_approval(edit["session_id"])
    preview = json.loads(edit["approval"]["summary"])
    console.approve(edit)
    edit = console.wait_for_terminal(edit["session_id"])
    reversal = console.reversal(edit["session_id"])
    undo = console.undo(
        edit["session_id"], "phase19-undo", reversal["expected_revision"],
    )
    undo = console.wait_for_approval(undo["session_id"])
    undo_preview = json.loads(undo["approval"]["summary"])
    console.approve(undo)
    undo = console.wait_for_terminal(undo["session_id"])
    return {
        "summary_grounded": summary["result"]["assurance"] in {"grounded", "verified"},
        "summary_content_sha256": _digest(summary["result"]["content"]),
        "test_verified": bool(test["result"]["verified"]),
        "edit_previewed": preview.get("document_uri") == target.as_uri()
        and preview.get("edits") == edit_parameters["edits"],
        "edit_verified": bool(edit["result"]["verified"]),
        "undo_verified": bool(undo["result"]["verified"]),
        "reversal_token_private": "reversal_token" not in undo_preview
        and "reversal_token" not in undo["result"]["content"],
        "undo_result_sha256": _digest(undo["result"]["content"]),
    }


def _project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Phase 19 project\nA local signed-install application-weaving test.\n",
        encoding="utf-8",
    )
    (project / "active.py").write_text('message = "before"\n', encoding="utf-8")
    (project / "test_active.py").write_text(
        "import unittest\n\nclass TestActive(unittest.TestCase):\n"
        "    def test_before(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )
    return project


def _edit_parameters(target: Path) -> dict:
    return {
        "document_uri": target.as_uri(),
        "edits": [{
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 18},
            },
            "new_text": 'message = "after"',
        }],
    }


def _console_context(value: dict) -> dict:
    return _context(
        value["context_id"], "application", value["resource_ref"],
        value["display_name"],
        ["vscode.editor.active", "vscode.workspace_edit.apply"],
    )


def _context(context_id, kind, resource_ref, display_name, capabilities):
    return {
        "context_id": context_id, "kind": kind, "resource_ref": resource_ref,
        "display_name": display_name, "capability_ids": capabilities,
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
