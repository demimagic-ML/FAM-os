"""Host-policy selection for the isolated verifier worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner, BubblewrapSettings
from fam_os.verification import IsolationLevel, SandboxRequest, SandboxStatus


FAM_USERNS_APPARMOR_PROFILE = "fam-os-userns"
_APPARMOR_ENABLED = Path("/sys/module/apparmor/parameters/enabled")
_USERNS_RESTRICTION = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")


@dataclass(frozen=True, slots=True)
class SandboxHostSecurityReceipt:
    healthy: bool
    apparmor_profile: str | None
    status: str
    isolation: str
    reason: str
    implementation_path: str


def required_sandbox_apparmor_profile(
    enabled_path: Path = _APPARMOR_ENABLED,
    restriction_path: Path = _USERNS_RESTRICTION,
) -> str | None:
    """Return the dedicated profile only when the host requires it."""
    try:
        enabled = enabled_path.read_text(encoding="utf-8").strip().lower()
        restricted = restriction_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if enabled in {"y", "yes", "1"} and restricted == "1":
        return FAM_USERNS_APPARMOR_PROFILE
    return None


def diagnose_verifier_sandbox() -> SandboxHostSecurityReceipt:
    profile = required_sandbox_apparmor_profile()
    result = BubblewrapSandboxRunner(BubblewrapSettings(
        apparmor_profile=profile,
    )).run(SandboxRequest("print('FAM_SANDBOX_READY')"))
    healthy = bool(
        result.status is SandboxStatus.COMPLETED
        and result.isolation is IsolationLevel.BUBBLEWRAP
        and result.exit_code == 0
        and result.stdout.strip() == "FAM_SANDBOX_READY"
    )
    return SandboxHostSecurityReceipt(
        healthy=healthy,
        apparmor_profile=profile,
        status=result.status.value,
        isolation=result.isolation.value,
        reason=result.reason,
        implementation_path=str(Path(__file__).resolve()),
    )
