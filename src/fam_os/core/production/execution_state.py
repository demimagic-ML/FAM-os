"""Shared durable inference state transitions."""

from dataclasses import replace

from fam_os.core.production.contracts import (
    AssuranceLevel,
    InferenceExecutionState,
)


def replace_execution(repositories, record, **changes):
    updated = replace(record, revision=record.revision + 1, **changes)
    if not repositories.inference_executions.replace(record.revision, updated):
        raise RuntimeError("inference execution revision conflict")
    return updated


def terminal_execution(
    repositories,
    record,
    failure_code=None,
    assurance=AssuranceLevel.UNVERIFIED,
    feedback="",
):
    return replace_execution(
        repositories, record, state=InferenceExecutionState.TERMINAL,
        assurance=assurance, failure_code=failure_code,
        verifier_feedback=feedback,
    )


def internal_capability(intent) -> str:
    return f"core.intent.{intent.value}"
