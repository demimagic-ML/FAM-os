"""Ollama adapter for authority-free mathematical reasoning."""

import json
from dataclasses import dataclass

from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceRuntime, MessageRole,
)
from fam_os.experts.math_experts import MathReasoningAdvice


@dataclass(frozen=True, slots=True)
class OllamaMathReasoner:
    runtime: InferenceRuntime
    model_ref: str
    context_tokens: int = 4096
    max_output_tokens: int = 384

    def reason(self, problem_id: str, prompt: str) -> MathReasoningAdvice:
        response = self.runtime.chat(self._request(prompt))
        try:
            return _parse(problem_id, self.model_ref, response.content)
        except ValueError as error:
            feedback = f"INVALID OUTPUT:\n{response.content}\nERROR: {error}"
            repaired = self.runtime.chat(self._request(prompt, feedback[:4000]))
            return _parse(problem_id, self.model_ref, repaired.content)

    def _request(self, prompt: str, feedback: str | None = None):
        user = prompt if feedback is None else f"{prompt}\n\nREPAIR:\n{feedback}"
        return InferenceRequest(
            self.model_ref,
            (InferenceMessage(MessageRole.SYSTEM, _SYSTEM),
             InferenceMessage(MessageRole.USER, user)),
            self.context_tokens, self.max_output_tokens, json_output=True,
        )


_SYSTEM = """Explain the mathematical reasoning. Return only JSON with non-empty
string keys explanation, proposed_expression, and proposed_answer. Your output is
advisory: an independent deterministic solver will compute the released result."""


def _parse(problem_id: str, model_ref: str, content: str) -> MathReasoningAdvice:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("math reasoning response must be JSON") from exc
    explanation = raw.get("explanation")
    expression = raw.get("proposed_expression")
    answer = raw.get("proposed_answer")
    values = (explanation, expression, answer)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError("math reasoning JSON fields must be non-empty strings")
    assert isinstance(explanation, str)
    assert isinstance(expression, str)
    assert isinstance(answer, str)
    return MathReasoningAdvice(problem_id, explanation, expression, answer, model_ref)
