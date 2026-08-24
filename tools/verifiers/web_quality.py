#!/usr/bin/python3
"""Deterministic bounded HTML/CSS syntax verifier for signed tool recipes."""

from html.parser import HTMLParser
from pathlib import Path
import re
import sys


class StrictHtmlParser(HTMLParser):
    VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.ids: set[str] = set()
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        identifier = attributes.get("id")
        if identifier and identifier in self.ids:
            self.errors.append(f"duplicate id: {identifier}")
        if identifier:
            self.ids.add(identifier)
        if tag == "img" and not attributes.get("alt"):
            self.errors.append("img requires nonempty alt text")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.errors.append(f"unbalanced closing tag: {tag}")

    def close(self):
        super().close()
        if self.stack:
            self.errors.append("unclosed tags: " + ",".join(self.stack))


def verify_html(content: str) -> tuple[str, ...]:
    parser = StrictHtmlParser()
    try:
        parser.feed(content)
        parser.close()
    except Exception as error:
        return (f"HTML parser error: {error}",)
    if "<!doctype html>" not in content[:256].lower():
        parser.errors.append("HTML document requires a doctype")
    return tuple(parser.errors)


def verify_css(content: str) -> tuple[str, ...]:
    stripped = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    errors: list[str] = []
    if stripped.count("{") != stripped.count("}"):
        errors.append("CSS braces are unbalanced")
    for index, block in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", stripped), 1):
        selector, declarations = block
        if not selector.strip():
            errors.append(f"CSS block {index} has no selector")
        for declaration in filter(str.strip, declarations.split(";")):
            if ":" not in declaration:
                errors.append(f"CSS block {index} has invalid declaration")
    if re.search(r"expression\s*\(|javascript\s*:", stripped, re.IGNORECASE):
        errors.append("CSS contains an unsafe executable construct")
    return tuple(errors)


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"html", "css"}:
        print("usage: web_quality.py html|css PATH", file=sys.stderr)
        return 2
    path = Path(argv[2])
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_048_576:
        print("input must be a bounded regular non-symlink file", file=sys.stderr)
        return 2
    content = path.read_text(encoding="utf-8")
    errors = verify_html(content) if argv[1] == "html" else verify_css(content)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
