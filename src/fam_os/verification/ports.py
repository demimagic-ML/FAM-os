"""Provider-neutral deterministic verifier port."""

from typing import Protocol

from fam_os.verification.contracts import VerificationReport, VerificationRequest


class Verifier(Protocol):
    def verify(self, request: VerificationRequest) -> VerificationReport: ...
