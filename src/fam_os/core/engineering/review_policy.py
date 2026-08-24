"""Deterministic selection of independent engineering review disciplines."""

from __future__ import annotations

import hashlib

from fam_os.core.engineering.review import (
    EngineeringReviewDiscipline,
    EngineeringReviewSelection,
)


class EngineeringReviewSelectionPolicy:
    """Select review disciplines from admitted intent and an exact changeset."""

    policy_id = "fam.engineering.review-selection.v1"

    _SECURITY_WORDS = frozenset({
        "auth", "credential", "encrypt", "permission", "privilege", "sandbox",
        "secret", "security", "token", "network", "socket", "exec", "shell",
    })
    _ARCHITECTURE_WORDS = frozenset({
        "architecture", "contract", "migration", "protocol", "schema",
        "storage", "database", "component", "public api", "adr",
    })
    _DESIGN_WORDS = frozenset({
        "design", "interface", "layout", "responsive", "ui", "ux",
        "visual", "accessibility", "animation", "typography",
    })
    _SECURITY_PATH_PARTS = (
        "auth", "credential", "crypto", "permission", "privileged", "sandbox",
        "secret", "security", "network", "socket", "shell", "supervisor",
    )
    _ARCHITECTURE_PATH_PREFIXES = (
        "docs/decisions/", "schemas/", "src/fam_os/schemas/",
        "src/fam_os/product/storage/migrations/",
    )
    _DESIGN_SUFFIXES = (
        ".css", ".scss", ".sass", ".less", ".svg", ".png", ".jpg",
        ".jpeg", ".webp", ".gif", ".fig", ".sketch",
    )

    def select(self, definition, changeset) -> EngineeringReviewSelection:
        intent = " ".join(definition.task.intent.lower().split())
        words = frozenset(intent.replace("-", " ").replace("/", " ").split())
        paths = tuple(item.path.lower() for item in changeset.preview.items)
        risks = tuple(
            risk.lower()
            for item in changeset.preview.items
            for risk in item.risk_codes
        )
        disciplines = [EngineeringReviewDiscipline.CODE]
        if (
            words & self._SECURITY_WORDS
            or any(part in path for path in paths for part in self._SECURITY_PATH_PARTS)
            or any(risk in {"set_executable", "binary_asset"} for risk in risks)
        ):
            disciplines.append(EngineeringReviewDiscipline.SECURITY)
        if (
            any(term in intent for term in self._ARCHITECTURE_WORDS)
            or any(path.startswith(self._ARCHITECTURE_PATH_PREFIXES) for path in paths)
        ):
            disciplines.append(EngineeringReviewDiscipline.ARCHITECTURE)
        if (
            words & self._DESIGN_WORDS
            or any(path.endswith(self._DESIGN_SUFFIXES) for path in paths)
            or any("/static/" in f"/{path}" for path in paths)
        ):
            disciplines.append(EngineeringReviewDiscipline.DESIGN)
        preview_sha256 = _preview_digest(changeset)
        intent_sha256 = hashlib.sha256(
            definition.task.intent.encode("utf-8")
        ).hexdigest()
        selection_id = _identity(
            "review-selection", definition.task.task_id,
            changeset.candidate_id, preview_sha256, self.policy_id,
            intent_sha256, *(item.value for item in disciplines),
        )
        return EngineeringReviewSelection(
            selection_id, definition.task.task_id, changeset.candidate_id,
            preview_sha256, self.policy_id, intent_sha256,
            tuple(disciplines), definition.created_at,
        )


def _preview_digest(changeset) -> str:
    from fam_os.core.engineering.candidate_changeset import candidate_preview_digest

    return candidate_preview_digest(changeset.preview)


def _identity(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"
