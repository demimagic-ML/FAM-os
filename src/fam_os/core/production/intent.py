"""Policy-owned deterministic intent classification for installed requests."""

from __future__ import annotations

import re

from fam_os.core.production.contracts import ModelIntent
from fam_os.routing import RouteName


class DeterministicIntentClassifier:
    """Classify conservatively; model advice never grants application authority."""

    def classify(
        self,
        prompt: str,
        required_capabilities: tuple[str, ...] = (),
    ) -> ModelIntent:
        normalized = " ".join(prompt.lower().split())
        if any(_mutation_capability(value) for value in required_capabilities):
            return ModelIntent.APPLICATION_MUTATION
        if required_capabilities:
            return ModelIntent.READ_ONLY_TASK
        for intent, patterns in _PATTERNS:
            if any(re.search(pattern, normalized) for pattern in patterns):
                return intent
        return ModelIntent.CONVERSATION

    @staticmethod
    def route(intent: ModelIntent) -> RouteName:
        if intent is ModelIntent.CODE:
            return RouteName.CODE
        if intent is ModelIntent.MATH:
            return RouteName.MATH
        if intent in {ModelIntent.RETRIEVAL, ModelIntent.GROUNDED_QUESTION}:
            return RouteName.RETRIEVAL
        return RouteName.KERNEL


_PATTERNS = (
    (ModelIntent.MEDIA, (r"\b(image|photo|screenshot|video|audio|ocr|transcribe)\b",)),
    (ModelIntent.ADMINISTRATION, (r"\b(install|update|service|daemon|systemd|permission)\b",)),
    (ModelIntent.CODE, (r"\b(code|function|class|bug|test|python|typescript|compile)\b",)),
    (ModelIntent.MATH, (r"\b(calculate|equation|integral|derivative|theorem|probability)\b", r"\d\s*[+*/^=]\s*\d")),
    (ModelIntent.RETRIEVAL, (r"\b(search|find|look up|retrieve)\b",)),
    (ModelIntent.GROUNDED_QUESTION, (
        r"\b(this project|these files|current repository|cite)\b",
        r"\b(?:in|inside|within|from)\s+(?:this|my|the current)\s+"
        r"(?:workspace|repository|project|folder|document|files?)\b",
        r"\b(?:this|my|the current)\s+"
        r"(?:workspace|repository|project|folder|document|files?)\b",
        r"\b(fam[\s_-]*os|for all mankind operating system)\b",
    )),
)


def _mutation_capability(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in (
        "write", "edit", "delete", "execute", "apply", "create", "remove",
        "move", "rename", "copy", "launch", "save", "undo", "patch", "restore",
    ))
