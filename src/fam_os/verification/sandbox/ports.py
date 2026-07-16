"""Sandbox execution port."""

from typing import Protocol

from fam_os.verification.sandbox.contracts import SandboxRequest, SandboxResult


class SandboxRunner(Protocol):
    def run(self, request: SandboxRequest) -> SandboxResult: ...
