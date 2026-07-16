"""Explicit verifier-owned context that may be disclosed to repair experts."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepairContext:
    trusted_test_source: str = ""
    failure_examples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(self.trusted_test_source) > 32_000:
            raise ValueError("repair test source exceeds the disclosure bound")
        if any(not item.strip() or len(item) > 4_000 for item in self.failure_examples):
            raise ValueError("repair examples must be non-empty and bounded")
        if sum(map(len, self.failure_examples)) > 16_000:
            raise ValueError("repair examples exceed the aggregate bound")
