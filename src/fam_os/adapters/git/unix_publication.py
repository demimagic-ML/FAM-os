"""Credential-opaque provider-neutral publication broker client."""

import os
import socket
import stat
from pathlib import Path

from fam_os.core.engineering.git_delivery import GitPublicationApproval, GitPublicationReceipt
from fam_os.core.engineering.git_publication_proposal import (
    GitRemoteRefObservation, GitRemoteRefObservationRequest,
)
from fam_os.schemas import dumps_document, loads_document


class UnixGitPublicationBroker:
    def __init__(self, socket_path: Path, *, maximum_response_bytes: int = 1_048_576) -> None:
        if not socket_path.is_absolute():
            raise ValueError("Git publication broker socket must be absolute")
        self._path = socket_path
        self._limit = maximum_response_bytes

    def publish(self, approval: GitPublicationApproval) -> GitPublicationReceipt:
        # The wire document carries only an opaque credential_ref. The broker
        # owns provider authentication and never returns credential material.
        result = self._exchange(approval)
        if not isinstance(result, GitPublicationReceipt):
            raise TypeError("Git publication broker returned an unexpected contract")
        return result

    def observe(
        self, request: GitRemoteRefObservationRequest,
    ) -> GitRemoteRefObservation:
        """Observe one exact remote ref without returning credential material."""
        result = self._exchange(request)
        if not isinstance(result, GitRemoteRefObservation):
            raise TypeError("Git publication broker returned an unexpected observation")
        return result

    def _exchange(self, value):
        self._require_socket()
        request = (dumps_document(value) + "\n").encode()
        if len(request) > self._limit:
            raise ValueError("Git publication request exceeds transport bound")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(60)
            client.connect(str(self._path))
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            response = bytearray()
            while len(response) <= self._limit:
                part = client.recv(min(65_536, self._limit + 1 - len(response)))
                if not part:
                    break
                response.extend(part)
        if len(response) > self._limit:
            raise ValueError("Git publication response exceeds transport bound")
        return loads_document(response.decode())

    def _require_socket(self) -> None:
        details = self._path.stat(follow_symlinks=False)
        if self._path.is_symlink() or not stat.S_ISSOCK(details.st_mode):
            raise PermissionError("Git publication broker endpoint is not a real socket")
        if details.st_uid not in {0, os.geteuid()}:
            raise PermissionError("Git publication broker owner is not trusted")
        if stat.S_IMODE(details.st_mode) != 0o600:
            raise PermissionError("Git publication broker mode must be 0600")
