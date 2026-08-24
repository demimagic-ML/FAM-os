"""Strict parsing of model-proposed application action parameters."""

import json


def parse_action_parameters(content: str) -> dict:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("candidate is not JSON") from error
    if not isinstance(value, dict):
        raise ValueError("candidate must be a JSON object")
    return value
