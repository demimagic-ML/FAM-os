#!/usr/bin/env python3
"""Validate connector-owned capability schemas and representative values."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]


def main() -> int:
    paths = tuple(sorted((ROOT / "schemas").glob("*.schema.json")))
    if len(paths) != 8:
        raise RuntimeError("expected eight VS Code capability schemas")
    schemas = {path.stem.removesuffix(".schema"): json.loads(path.read_text()) for path in paths}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    Draft202012Validator(schemas["vscode.editor.selection.input.v1"]).validate(
        {"maximum_characters": 4096}
    )
    Draft202012Validator(schemas["vscode.workspace_edit.input.v1"]).validate({
        "document_uri": "file:///workspace/example.ts",
        "edits": [{
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": 0, "character": 1},
            },
            "new_text": "replacement",
        }],
    })
    Draft202012Validator(schemas["vscode.workspace_edit.input.v1"]).validate(
        {"reversal_token": "token-1"}
    )
    print("validated 8 VS Code capability schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
