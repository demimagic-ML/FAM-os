"""Pure prompt builders for initial generation and bounded repair."""

from fam_os.core.ports.inference import InferenceMessage, MessageRole
from fam_os.core.execution.repair_context import RepairContext
from fam_os.verification.contracts import VerificationReport


def expert_messages(prompt: str) -> tuple[InferenceMessage, ...]:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    return (
        InferenceMessage(
            MessageRole.SYSTEM,
            "You are a coding specialist in a verified local AI runtime. "
            "Return one Python code block containing the complete implementation. "
            "Do not claim success without satisfying every requirement.",
        ),
        InferenceMessage(MessageRole.USER, prompt),
    )


def repair_messages(
    prompt: str,
    candidate: str,
    failure: VerificationReport,
    guidance: str = "",
    context: RepairContext = RepairContext(),
) -> tuple[InferenceMessage, ...]:
    if not prompt.strip() or not candidate.strip():
        raise ValueError("prompt and candidate must not be empty")
    details = failure.failure_details(4_000)
    disclosed = _repair_context(context)
    return (
        InferenceMessage(
            MessageRole.SYSTEM,
            "Repair Python code using deterministic verifier feedback. "
            "Return only one complete Python code block.",
        ),
        InferenceMessage(
            MessageRole.USER,
            f"Original request:\n{prompt}\n\n"
            f"Candidate that failed:\n{candidate}\n\n"
            f"Verifier failure:\n{details}\n\n"
            f"Verifier-owned repair context:\n{disclosed}\n\n"
            f"Verifier guidance:\n{guidance or 'Use the failure and original requirements.'}\n\n"
            "Trace the failure against every disclosed case, then correct the general "
            "implementation without hardcoding examples and without weakening any requirement.",
        ),
    )


def _repair_context(context: RepairContext) -> str:
    sections = []
    if context.trusted_test_source:
        sections.append(f"Trusted test source:\n{context.trusted_test_source}")
    if context.failure_examples:
        examples = "\n".join(
            f"{index}. {example}" for index, example in enumerate(
                context.failure_examples, start=1
            )
        )
        sections.append(f"Required input/output examples:\n{examples}")
    return "\n\n".join(sections) or "No additional verifier context was disclosed."
