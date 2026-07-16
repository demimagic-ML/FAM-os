"""Core execution domain exceptions."""


class ExecutionConfigurationError(RuntimeError):
    """Raised when execution policy references an unavailable expert."""
