"""Reusable workflow recipes, including ten immediately useful built-ins."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


BUILTIN_RECIPES = (
    ("builtin.pdf-summary", "Summarize PDFs", "Summarize every PDF in a selected folder.", "documents.summarize-pdf", "Summarize the important points, decisions, and action items."),
    ("builtin.pdf-decisions", "Extract decisions from PDFs", "Create a decision-focused document brief.", "documents.summarize-pdf", "Focus on decisions, owners, dates, and unresolved questions."),
    ("builtin.csv-profile", "Profile a CSV", "Create numeric statistics and a chart.", "data.analyze-csv", "Analyze the dataset and highlight unusual values."),
    ("builtin.csv-kpis", "Report CSV KPIs", "Create a concise KPI-oriented report.", "data.analyze-csv", "Summarize the principal numeric KPIs and trends."),
    ("builtin.meeting-transcript", "Transcribe a meeting", "Create a local meeting transcript.", "media.transcribe-audio", "Transcribe the meeting and retain speaker-neutral text."),
    ("builtin.audio-actions", "Audio action items", "Transcribe audio for decisions and follow-ups.", "media.transcribe-audio", "Transcribe and identify decisions, owners, and action items."),
    ("builtin.research-brief", "Cited research brief", "Summarize supplied web sources with links.", "research.cited-brief", "Create a concise cited research brief."),
    ("builtin.competitor-brief", "Competitor source brief", "Compare supplied competitor sources.", "research.cited-brief", "Compare claims, positioning, strengths, and gaps across the sources."),
    ("builtin.repo-fix", "Fix a repository issue", "Prepare, verify, and review a code change.", "engineering.issue-to-change", "Implement the requested fix, run focused tests, and prepare the exact change for review."),
    ("builtin.repo-review", "Review and improve a repository", "Analyze a repository and prepare a bounded improvement.", "engineering.issue-to-change", "Find the highest-impact implementation weakness, fix it, and verify the result."),
)


class RecipeLibrary:
    def __init__(self, database, tasks) -> None:
        self._database = database
        self._tasks = tasks

    def list(self) -> dict[str, list[dict[str, object]]]:
        builtins = [_builtin(item) for item in BUILTIN_RECIPES]
        rows = self._database.fetchall(
            "SELECT recipe_id,name,description,request_template_json,created_at,updated_at,"
            "source_task_id FROM useful_recipes ORDER BY updated_at DESC",
        )
        custom = [{
            "recipe_id": row[0], "name": row[1], "description": row[2],
            "request_template": json.loads(row[3]), "created_at": row[4],
            "updated_at": row[5], "source_task_id": row[6], "builtin": False,
        } for row in rows]
        return {"recipes": builtins + custom}

    def create(self, document: dict) -> dict[str, object]:
        name, description = _text(document, "name"), _text(document, "description")
        template = document.get("request_template")
        if not isinstance(template, dict) or not isinstance(template.get("workflow_id"), str):
            raise ValueError("recipe request_template requires a workflow_id")
        identifier, now = str(uuid4()), _now()
        self._database.execute(
            "INSERT INTO useful_recipes VALUES(?,?,?,?,?,?,?)",
            (
                identifier, name, description, json.dumps(template, sort_keys=True),
                now, now, document.get("source_task_id"),
            ),
        )
        return self.inspect(identifier)

    def inspect(self, recipe_id: str) -> dict[str, object]:
        for item in self.list()["recipes"]:
            if item["recipe_id"] == recipe_id:
                return item
        raise KeyError("recipe was not found")

    def run(self, recipe_id: str, inputs: dict) -> dict[str, object]:
        if not isinstance(inputs, dict):
            raise ValueError("recipe inputs must be an object")
        recipe: dict[str, Any] = self.inspect(recipe_id)
        template = recipe["request_template"]
        if not isinstance(template, dict):
            raise ValueError("stored recipe template is invalid")
        request = dict(template)
        allowed = {"prompt", "workspace_root", "input_paths", "urls", "project_id"}
        if set(inputs) - allowed:
            raise ValueError("recipe inputs contain unsupported fields")
        request.update(inputs)
        return self._tasks.run(request)


def _builtin(item) -> dict[str, object]:
    return {
        "recipe_id": item[0], "name": item[1], "description": item[2],
        "request_template": {"workflow_id": item[3], "prompt": item[4]},
        "created_at": None, "updated_at": None, "source_task_id": None,
        "builtin": True,
    }


def _text(document, name):
    value = document.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
