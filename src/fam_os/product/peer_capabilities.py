"""Signed peer declarations derived from the enabled installed runtime catalog."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from fam_os.core.production.contracts import ModelIntent
from fam_os.fabric import create_capability_declaration

_CAPABILITY_BY_INTENT = {
    ModelIntent.CONVERSATION: "language.generate",
    ModelIntent.GROUNDED_QUESTION: "retrieval.grounded-answer",
    ModelIntent.READ_ONLY_TASK: "language.analyze",
    ModelIntent.APPLICATION_MUTATION: "application.plan",
    ModelIntent.CODE: "code.generate",
    ModelIntent.MATH: "math.solve",
    ModelIntent.RETRIEVAL: "retrieval.query",
    ModelIntent.MEDIA: "vision.analyze",
    ModelIntent.ADMINISTRATION: "kernel.administer",
}


def capability_for_intent(intent: ModelIntent) -> str:
    return _CAPABILITY_BY_INTENT[intent]


def catalog_capability_source(catalog):
    scoped = tuple(
        (item, catalog.entry_for_provenance(item))
        for item in catalog.provenances()
    )
    represented = {item.model_ref for item, _ in scoped}
    declarations_to_issue = tuple(
        (item.expert_id, entry) for item, entry in scoped
    ) + tuple(
        ("runtime-" + entry.manifest_sha256[:24], entry)
        for entry in catalog.entries() if entry.model_ref not in represented
    )

    def declarations(credentials, observed_at):
        revision = max(1, int(observed_at.timestamp() * 1_000_000))
        values = []
        for expert_id, entry in declarations_to_issue:
            identity = hashlib.sha256(
                f"{credentials.identity.device_id}|{expert_id}|{revision}".encode(),
            ).hexdigest()[:32]
            values.append(create_capability_declaration(
                credentials, declaration_id="capability-" + identity,
                expert_id=expert_id, model_ref=entry.model_ref,
                expert_tier=entry.tier,
                capability_ids=tuple(_CAPABILITY_BY_INTENT[item] for item in entry.intents),
                maximum_context_bytes=entry.max_context_tokens * 4,
                manifest_sha256=entry.manifest_sha256, revision=revision,
                issued_at=observed_at, expires_at=observed_at + timedelta(hours=24),
            ))
        return tuple(values)

    return declarations
