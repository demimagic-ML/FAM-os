"""Strict Server-Sent Events resume cursor parsing."""


def event_id(value: str | None) -> int:
    if value is None:
        return -1
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError("Last-Event-ID must be an integer") from error
    if parsed < -1:
        raise ValueError("Last-Event-ID cannot be less than -1")
    return parsed
