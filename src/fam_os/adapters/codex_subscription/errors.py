"""Stable failures for the Codex subscription boundary."""


class CodexSubscriptionError(RuntimeError):
    """The authenticated Codex runtime failed inside its bounded contract."""
