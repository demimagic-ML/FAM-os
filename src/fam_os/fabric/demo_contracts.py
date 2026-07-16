"""Three-device trusted-fabric demonstration evidence."""

from dataclasses import dataclass

FABRIC_DEMO_CONTRACT_VERSION = "fam.fabric.demo/v1alpha1"


@dataclass(frozen=True, slots=True)
class MultiDeviceDemoReport:
    report_id: str
    enrolled_device_ids: tuple[str, ...]
    encrypted_transport: bool
    remote_device_selected: str
    unauthorized_context_bytes: int
    remote_result_verified: bool
    disconnect_local_fallback_verified: bool
    passed: bool
    contract_version: str = FABRIC_DEMO_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = len(self.enrolled_device_ids) == 3 and self.encrypted_transport
        expected = expected and self.unauthorized_context_bytes == 0
        expected = expected and self.remote_result_verified and self.disconnect_local_fallback_verified
        if self.passed != expected:
            raise ValueError("multi-device demo report does not satisfy exit evidence")
