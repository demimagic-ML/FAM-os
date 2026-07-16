"""Prompt used by the historical expert-activation measurement."""

from fam_os.core.ports.inference import InferenceMessage, MessageRole


def activation_messages(prompt: str) -> tuple[InferenceMessage, ...]:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    return (
        InferenceMessage(
            MessageRole.SYSTEM,
            "You are the activated coding specialist. Solve the request directly and concisely.",
        ),
        InferenceMessage(MessageRole.USER, prompt),
    )
