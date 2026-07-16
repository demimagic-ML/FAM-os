"""Prepared shell-free OpenURI desktop-portal action adapter."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.deterministic_result import DeterministicAdapterResult


@dataclass(frozen=True, slots=True)
class PortalOpenUriPolicy:
    allowed_schemes: tuple[str, ...]
    gdbus_executable: Path = Path("/usr/bin/gdbus")
    environment: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.allowed_schemes or len(set(self.allowed_schemes)) != len(
            self.allowed_schemes
        ):
            raise ValueError("portal URI schemes must be unique and non-empty")
        if any(not item.islower() or not item.isalpha() for item in self.allowed_schemes):
            raise ValueError("portal URI schemes must be lowercase letters")
        if not self.gdbus_executable.is_absolute():
            raise ValueError("portal gdbus executable must be absolute")
        if len({key for key, _ in self.environment}) != len(self.environment):
            raise ValueError("portal environment keys must be unique")


@dataclass(frozen=True, slots=True)
class PortalOpenProposal:
    operation_id: str
    uri: str

    def __post_init__(self) -> None:
        if not self.operation_id.strip() or not self.uri.strip():
            raise ValueError("portal proposal identity must not be empty")


class DesktopPortalAdapter:
    capability_id = "linux.portal.open_uri"

    def __init__(self, policy: PortalOpenUriPolicy, runner=None):
        self._policy = policy
        self._runner = runner or BoundedSubprocessRunner()

    def prepare_open_uri(self, operation_id: str, uri: str):
        parsed = urlsplit(uri)
        if parsed.scheme not in self._policy.allowed_schemes:
            raise PermissionError("URI scheme is not allowed by portal policy")
        if parsed.scheme != "file" and not parsed.netloc:
            raise ValueError("portal URI requires an authority")
        if parsed.username is not None or parsed.password is not None or "\0" in uri:
            raise ValueError("portal URI cannot contain credentials or null bytes")
        return PortalOpenProposal(operation_id, uri)

    def probe(self):
        try:
            result = self._runner.run(
                _probe_command(self._policy.gdbus_executable),
                environment=dict(self._policy.environment),
            )
        except Exception:
            return _failed("portal.unavailable")
        if not result.succeeded:
            return _failed("portal.unavailable")
        return DeterministicAdapterResult(
            self.capability_id, True,
            {"available": True, "version_reply": result.stdout.strip()},
        )

    def open_uri(self, proposal: PortalOpenProposal):
        validated = self.prepare_open_uri(proposal.operation_id, proposal.uri)
        try:
            result = self._runner.run(
                _open_uri_command(self._policy.gdbus_executable, validated.uri),
                environment=dict(self._policy.environment),
            )
        except Exception:
            return _failed("portal.provider_failure")
        if not result.succeeded:
            code = "portal.output_limit" if result.output_limited else "portal.request_failed"
            return _failed(code)
        return DeterministicAdapterResult(
            self.capability_id, True, {"request": result.stdout.strip()}
        )


def _open_uri_command(executable, uri):
    return (
        str(executable), "call", "--session",
        "--dest", "org.freedesktop.portal.Desktop",
        "--object-path", "/org/freedesktop/portal/desktop",
        "--method", "org.freedesktop.portal.OpenURI.OpenURI",
        "", uri, "{}",
    )


def _probe_command(executable):
    return (
        str(executable), "call", "--session",
        "--dest", "org.freedesktop.portal.Desktop",
        "--object-path", "/org/freedesktop/portal/desktop",
        "--method", "org.freedesktop.DBus.Properties.Get",
        "org.freedesktop.portal.OpenURI", "version",
    )


def _failed(code):
    return DeterministicAdapterResult(
        DesktopPortalAdapter.capability_id, False, {}, code
    )
