#!/usr/bin/env python3
"""Render or verify deterministic JSON Schema artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.schemas import SCHEMA_DESCRIPTORS, build_schema


def render(schema_root: Path, *, check: bool) -> tuple[str, ...]:
    mismatches: list[str] = []
    schema_root.mkdir(parents=True, exist_ok=True)
    expected_paths: set[Path] = set()
    for descriptor in SCHEMA_DESCRIPTORS:
        family, version = descriptor.schema_id.rsplit("/", 1)
        relative_path = Path(version) / f"{family}.schema.json"
        expected_paths.add(relative_path)
        path = schema_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(build_schema(descriptor), indent=2, sort_keys=True) + "\n"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                mismatches.append(str(relative_path))
        else:
            path.write_text(content, encoding="utf-8")
    for path in schema_root.glob("v1alpha*/*.schema.json"):
        relative_path = path.relative_to(schema_root)
        if relative_path not in expected_paths:
            mismatches.append(str(relative_path))
    return tuple(sorted(mismatches))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("schemas"))
    args = parser.parse_args()
    mismatches = render(args.output, check=args.check)
    if mismatches:
        print("schema artifacts differ: " + ", ".join(mismatches))
        return 1
    print(f"validated {len(SCHEMA_DESCRIPTORS)} schema artifacts" if args.check else f"rendered {len(SCHEMA_DESCRIPTORS)} schema artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
