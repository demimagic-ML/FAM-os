"""Aggregate reliability, security, and productization exit evidence."""

from dataclasses import asdict, dataclass


PHASE14_EXIT_VERSION = "fam.product.phase14-exit/v1alpha1"


@dataclass(frozen=True, slots=True)
class Phase14ExitEvidence:
    security_review_passed: bool
    atomic_update_and_rollback_passed: bool
    user_isolation_and_recovery_passed: bool
    extended_soak_passed: bool
    install_diagnose_repair_remove_passed: bool
    shell_console_visibility_passed: bool
    reference_benchmarks_passed: bool
    soak_sha256: str
    benchmark_sha256: str
    passed: bool
    contract_version: str = PHASE14_EXIT_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def phase14_exit(**values: object) -> Phase14ExitEvidence:
    checks = tuple(bool(values[name]) for name in (
        "security_review_passed", "atomic_update_and_rollback_passed",
        "user_isolation_and_recovery_passed", "extended_soak_passed",
        "install_diagnose_repair_remove_passed", "shell_console_visibility_passed",
        "reference_benchmarks_passed",
    ))
    return Phase14ExitEvidence(**values, passed=all(checks))  # type: ignore[arg-type]
