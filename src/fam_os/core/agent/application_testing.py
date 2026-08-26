"""Typed plans and evidence for model-driven application testing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ApplicationAssertionKind(StrEnum):
    TEXT = "text"
    URL = "url"
    ELEMENT = "element"
    CONSOLE_ERRORS = "console_errors"
    NETWORK_FAILURES = "network_failures"


@dataclass(frozen=True, slots=True)
class ApplicationTestCheck:
    check_id: str
    description: str
    kind: ApplicationAssertionKind
    expected: str

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.description.strip():
            raise ValueError("application test check identity is required")
        if not isinstance(self.kind, ApplicationAssertionKind):
            raise ValueError("application test assertion kind is invalid")


@dataclass(frozen=True, slots=True)
class ApplicationTestPlan:
    objective: str
    checks: tuple[ApplicationTestCheck, ...]
    artifacts: tuple[str, ...] = (
        "assertion_receipts", "final_screenshot", "browser_trace",
        "console_summary", "network_summary",
    )

    def __post_init__(self) -> None:
        if not self.objective.strip() or not self.checks:
            raise ValueError("application test plan requires an objective and checks")
        identifiers = [item.check_id for item in self.checks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("application test check IDs must be unique")


class ApplicationTestingObjectiveCompiler:
    """Compile an objective into harness-owned checks, not model-owned state."""

    def compile(
        self, objective: str, proposed_checks: tuple[dict[str, str], ...] = (),
    ) -> ApplicationTestPlan:
        if not objective.strip():
            raise ValueError("application test objective is required")
        checks = tuple(
            ApplicationTestCheck(
                item.get("check_id", f"check-{index}"),
                item["description"],
                ApplicationAssertionKind(item["kind"]),
                item.get("expected", ""),
            )
            for index, item in enumerate(proposed_checks, 1)
        )
        if not checks:
            checks = self._baseline(objective)
        required = {
            ApplicationAssertionKind.CONSOLE_ERRORS,
            ApplicationAssertionKind.NETWORK_FAILURES,
        }
        present = {item.kind for item in checks}
        additions = tuple(
            ApplicationTestCheck(
                kind.value, f"No {kind.value.replace('_', ' ')} are present.",
                kind, "0",
            )
            for kind in sorted(required - present, key=str)
        )
        return ApplicationTestPlan(objective, (*checks, *additions))

    @staticmethod
    def _baseline(objective: str) -> tuple[ApplicationTestCheck, ...]:
        normalized = objective.casefold()
        if "calculator" in normalized:
            values = (
                ("addition", "Addition produces the expected result."),
                ("subtraction", "Subtraction produces the expected result."),
                ("multiplication", "Multiplication produces the expected result."),
                ("division", "Division produces the expected result."),
                ("clear", "Clear resets the calculator display."),
                ("keyboard", "Keyboard input operates the calculator."),
            )
            return tuple(
                ApplicationTestCheck(key, description, ApplicationAssertionKind.TEXT, "")
                for key, description in values
            )
        return (ApplicationTestCheck(
            "requested-outcome", objective.strip(), ApplicationAssertionKind.TEXT, "",
        ),)
