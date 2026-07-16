"""Conservative SPDX license-expression syntax and allow-policy evaluation."""

from __future__ import annotations

import re


_TOKEN = re.compile(
    r"DocumentRef-[A-Za-z0-9.-]+:LicenseRef-[A-Za-z0-9.-]+"
    r"|LicenseRef-[A-Za-z0-9.-]+"
    r"|[A-Za-z0-9][A-Za-z0-9.-]*\+?"
    r"|\(|\)"
)
_OPERATORS = frozenset({"AND", "OR", "WITH"})


def validate_spdx_expression(expression: str, *, allow_references: bool = False) -> None:
    """Validate bounded SPDX expression grammar without guessing license aliases."""

    tokens = _tokenize(expression)
    parser = _Parser(tokens, allow_references)
    parser.parse_expression()
    if parser.position != len(tokens):
        raise ValueError("SPDX license expression has trailing tokens")


def require_allowed_license(
    expression: str,
    allowed: tuple[str, ...],
    *,
    allow_references: bool = False,
) -> None:
    validate_spdx_expression(expression, allow_references=allow_references)
    if expression not in allowed:
        raise PermissionError("package license is not allowed by policy")


class _Parser:
    def __init__(self, tokens: tuple[str, ...], allow_references: bool) -> None:
        self.tokens = tokens
        self.allow_references = allow_references
        self.position = 0

    def parse_expression(self) -> None:
        self._parse_and()
        while self._take("OR"):
            self._parse_and()

    def _parse_and(self) -> None:
        self._parse_primary()
        while self._take("AND"):
            self._parse_primary()

    def _parse_primary(self) -> None:
        if self._take("("):
            self.parse_expression()
            self._require(")")
            return
        self._parse_simple()

    def _parse_simple(self) -> None:
        identifier = self._next()
        if identifier in _OPERATORS or identifier in {"(", ")"}:
            raise ValueError("SPDX license expression expected a license identifier")
        if "LicenseRef-" in identifier and not self.allow_references:
            raise ValueError("SPDX LicenseRef is disabled by policy")
        if self._take("WITH"):
            exception = self._next()
            if exception in _OPERATORS or exception in {"(", ")"} or exception.endswith("+"):
                raise ValueError("SPDX WITH requires an exception identifier")

    def _next(self) -> str:
        if self.position >= len(self.tokens):
            raise ValueError("SPDX license expression ended unexpectedly")
        value = self.tokens[self.position]
        self.position += 1
        return value

    def _take(self, expected: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == expected:
            self.position += 1
            return True
        return False

    def _require(self, expected: str) -> None:
        if not self._take(expected):
            raise ValueError(f"SPDX license expression requires {expected}")


def _tokenize(expression: str) -> tuple[str, ...]:
    if expression != expression.strip() or not expression or len(expression) > 256:
        raise ValueError("SPDX license expression is not bounded canonical text")
    tokens: list[str] = []
    position = 0
    for match in _TOKEN.finditer(expression):
        if expression[position : match.start()].strip():
            raise ValueError("SPDX license expression contains invalid syntax")
        tokens.append(match.group())
        position = match.end()
    if expression[position:].strip() or not tokens or len(tokens) > 64:
        raise ValueError("SPDX license expression contains invalid syntax")
    return tuple(tokens)
