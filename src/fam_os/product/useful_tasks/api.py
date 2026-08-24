"""Authenticated facade for concrete user-facing workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from pathlib import Path
from uuid import uuid4

from fam_os.product.useful_tasks.artifacts import UsefulArtifactWriter
from fam_os.product.useful_tasks.builtins import (
    analyze_csv, engineering_task, research_urls, summarize_pdfs, transcribe_audio,
)
from fam_os.product.tool_loop import BoundedToolLoop, ToolRegistry, ToolResult, ToolStep


WORKFLOWS: tuple[dict[str, object], ...] = (
    {
        "workflow_id": "documents.summarize-pdf",
        "title": "Summarize PDFs",
        "description": "Extract up to 50 pages per PDF and create summary.md.",
        "accepts": [".pdf"],
    },
    {
        "workflow_id": "data.analyze-csv",
        "title": "Analyze a CSV",
        "description": "Create a Markdown profile and an SVG chart.",
        "accepts": [".csv"],
    },
    {
        "workflow_id": "media.transcribe-audio",
        "title": "Transcribe audio",
        "description": "Run the local speech expert and create transcript.md.",
        "accepts": [".wav", ".mp3", ".m4a", ".ogg", ".flac"],
    },
    {
        "workflow_id": "research.cited-brief",
        "title": "Create a cited research brief",
        "description": "Read supplied web sources and create research.md.",
        "accepts": [],
    },
    {
        "workflow_id": "engineering.issue-to-change",
        "title": "Implement a repository change",
        "description": "Enter the existing governed engineering lifecycle.",
        "accepts": [],
    },
)


class UsefulTaskApi:
    def __init__(
        self, repository, *, recognizer=None, engineering_delegate=None,
        identifier=None, clock=None,
        tool_loop_repository=None,
    ) -> None:
        self._repository = repository
        self._recognizer = recognizer
        self._engineering_delegate = engineering_delegate
        self._identifier = identifier or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._tool_loop_repository = tool_loop_repository
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fam-useful-task")
        self._futures: dict[str, Future] = {}
        self._lock = RLock()

    def workflows(self) -> tuple[dict[str, object], ...]:
        return WORKFLOWS

    def run(
        self, document: dict, *, parent_task_id: str | None = None,
    ) -> dict[str, object]:
        workflow_id = _text(document, "workflow_id")
        prompt = _text(document, "prompt")
        root = Path(_text(document, "workspace_root")).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("workspace_root must be a directory")
        if workflow_id not in {item["workflow_id"] for item in WORKFLOWS}:
            raise ValueError("unknown useful workflow")
        task_id = self._identifier()
        timestamp = self._timestamp()
        project_id = document.get("project_id")
        if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
            raise ValueError("project_id must be non-empty text")
        self._repository.create(
            task_id, workflow_id, prompt, root, timestamp, document,
            parent_task_id, project_id,
        )
        return self._execute_created(task_id, workflow_id, root, document)

    def submit(self, document: dict, *, parent_task_id: str | None = None) -> dict[str, object]:
        workflow_id = _text(document, "workflow_id")
        prompt = _text(document, "prompt")
        root = Path(_text(document, "workspace_root")).resolve(strict=True)
        if not root.is_dir() or workflow_id not in {item["workflow_id"] for item in WORKFLOWS}:
            raise ValueError("useful workflow or workspace is invalid")
        project_id = document.get("project_id")
        if project_id is not None and (not isinstance(project_id, str) or not project_id.strip()):
            raise ValueError("project_id must be non-empty text")
        task_id, timestamp = self._identifier(), self._timestamp()
        self._repository.create(task_id, workflow_id, prompt, root, timestamp, document,
                                parent_task_id, project_id, status="running")
        future = self._executor.submit(self._execute_background, task_id, workflow_id, root, document)
        with self._lock:
            self._futures[task_id] = future
        future.add_done_callback(lambda _future: self._forget(task_id))
        return self.inspect(task_id)

    def cancel(self, task_id: str) -> dict[str, object]:
        task = self.inspect(task_id)
        if task["status"] != "running":
            return task
        with self._lock:
            future = self._futures.get(task_id)
        if future is not None and future.cancel():
            self._repository.cancel(task_id, self._timestamp())
        else:
            raise RuntimeError("running workflow cannot be safely interrupted; cancellation is available before execution")
        return self.inspect(task_id)

    def projects(self) -> dict[str, object]:
        return {"projects": self._repository.projects()}

    def recipe_template(self, task_id: str) -> dict[str, object]:
        self.inspect(task_id)
        document = self._repository.request_document(task_id)
        return {key: value for key, value in document.items() if key not in {"workspace_root", "input_paths", "urls"}}

    def close(self) -> None:
        with self._lock:
            for task_id, future in tuple(self._futures.items()):
                if future.cancel():
                    self._repository.cancel(task_id, self._timestamp())
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _execute_background(self, task_id, workflow_id, root, document):
        if self.inspect(task_id)["status"] == "cancelled":
            return self.inspect(task_id)
        return self._execute_created(task_id, workflow_id, root, document)

    def _forget(self, task_id: str) -> None:
        with self._lock:
            self._futures.pop(task_id, None)

    def _execute_created(self, task_id, workflow_id, root, document):
        try:
            writer = UsefulArtifactWriter(root, task_id)
            if self._tool_loop_repository is None:
                summary, artifacts, continuation = self._execute(
                    workflow_id, root, document, writer,
                )
            else:
                summary, artifacts, continuation = self._run_tool_loop(
                    task_id, workflow_id, root, document, writer,
                )
            for artifact in artifacts:
                self._repository.add_artifact(artifact)
            self._repository.complete(task_id, summary, self._timestamp(), continuation)
        except Exception as error:
            self._repository.fail(task_id, _safe_error(error), self._timestamp())
        return self.inspect(task_id)

    def inspect(self, task_id: str) -> dict[str, object]:
        task = self._repository.get(task_id)
        if task is None:
            raise KeyError("useful task was not found")
        return task.to_dict()

    def list(
        self, *, limit: int = 50, offset: int = 0, query: str | None = None,
        project_id: str | None = None, attention_only: bool = False,
    ) -> dict[str, object]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("task list bounds are invalid")
        return {
            "tasks": [item.to_dict() for item in self._repository.list(
                limit=limit, offset=offset, query=query, project_id=project_id,
                attention_only=attention_only,
            )],
            "limit": limit,
            "offset": offset,
        }

    def retry(self, task_id: str) -> dict[str, object]:
        self.inspect(task_id)
        return self.run(self._repository.request_document(task_id), parent_task_id=task_id)

    def fork(self, task_id: str, overrides: dict) -> dict[str, object]:
        self.inspect(task_id)
        allowed = {"prompt", "workspace_root", "input_paths", "urls", "project_id"}
        if set(overrides) - allowed:
            raise ValueError("fork overrides contain unsupported fields")
        document = self._repository.request_document(task_id)
        document.update(overrides)
        return self.run(document, parent_task_id=task_id)

    def artifact(self, artifact_id: str):
        artifact = self._repository.artifact(artifact_id)
        path = artifact.path
        if not path.is_file() or path.stat().st_size != artifact.size_bytes:
            raise RuntimeError("useful artifact is unavailable or changed")
        return artifact

    def artifact_document(self, artifact_id: str) -> dict[str, object]:
        artifact = self.artifact(artifact_id)
        content = None
        if artifact.size_bytes <= 1_048_576 and (
            artifact.media_type.startswith("text/")
            or artifact.media_type in {"image/svg+xml", "application/json"}
        ):
            content = artifact.path.read_text(encoding="utf-8")
        document = artifact.to_dict()
        document["content"] = content
        return document

    def timeline(self, task_id: str) -> dict[str, object]:
        self.inspect(task_id)
        items = () if self._tool_loop_repository is None else self._tool_loop_repository.timeline(task_id)
        return {"task_id": task_id, "steps": items}

    def _run_tool_loop(self, task_id, workflow_id, root, document, writer):
        registry = ToolRegistry()
        registry.register("workflow.validate", lambda arguments: ToolResult({
            "workflow_id": arguments["workflow_id"], "workspace_root": str(root),
            "validated": True,
        }))

        def execute(_arguments):
            summary, artifacts, continuation = self._execute(
                workflow_id, root, document, writer,
            )
            return ToolResult(
                {"summary": summary, "continuation": continuation}, artifacts,
            )

        registry.register("workflow.execute", execute)
        results = BoundedToolLoop(registry, self._tool_loop_repository).run(task_id, (
            ToolStep("validate", "workflow.validate", {"workflow_id": workflow_id}),
            ToolStep("execute", "workflow.execute", {}),
        ))
        final = results[-1]
        return final.output["summary"], final.artifacts, final.output["continuation"]

    def _execute(self, workflow_id, root, document, writer):
        if workflow_id == "documents.summarize-pdf":
            return summarize_pdfs(root, document, writer)
        if workflow_id == "data.analyze-csv":
            return analyze_csv(root, document, writer)
        if workflow_id == "media.transcribe-audio":
            return transcribe_audio(root, document, writer, self._recognizer)
        if workflow_id == "research.cited-brief":
            return research_urls(root, document, writer)
        return engineering_task(
            root, document, writer, self._engineering_delegate,
        )

    def _timestamp(self) -> str:
        return self._clock().isoformat()


def _text(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > 16_384:
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _safe_error(error: Exception) -> str:
    if isinstance(error, (KeyError, PermissionError, RuntimeError, ValueError)):
        return str(error).strip("'")[:500]
    return "workflow failed unexpectedly"
