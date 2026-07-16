"""Prompt construction for the model-backed routing policy."""

from fam_os.core.ports.inference import InferenceMessage, MessageRole


ROUTER_SYSTEM_PROMPT = """You are the routing kernel for a modular local AI system.
Classify the user's request into exactly one route:
- kernel: ordinary language, rewriting, summarization, translation, or simple general knowledge
- code: programming, debugging, software design, code review, databases, or tests
- math: calculations, proofs, probability, algebra, calculus, or formal mathematical derivation
- retrieval: the answer depends on local files, repository contents, project notes, machine state, or information not included in the request

Return only a JSON object with this exact schema:
{"route":"kernel|code|math|retrieval","confidence":0.0,"reason":"short explanation"}
Do not answer the user's underlying request."""


def routing_messages(prompt: str) -> tuple[InferenceMessage, ...]:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    return (
        InferenceMessage(MessageRole.SYSTEM, ROUTER_SYSTEM_PROMPT),
        InferenceMessage(MessageRole.USER, prompt),
    )
