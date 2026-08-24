"""Length-bounded Unix-socket client for the separately privileged broker."""

import socket
from pathlib import Path

from fam_os.core.engineering.privileged import HostAdministrationChangeSet, HostAdministrationReceipt
from fam_os.schemas import dumps_document, loads_document


class UnixHostAdministrationBroker:
    def __init__(self, socket_path: Path, *, maximum_response_bytes: int = 1_048_576) -> None:
        if not socket_path.is_absolute():
            raise ValueError("host administration broker socket must be absolute")
        self._socket_path = socket_path
        self._limit = maximum_response_bytes

    def apply(self, change_set: HostAdministrationChangeSet, authentication_context_id: str) -> HostAdministrationReceipt:
        request = (dumps_document(change_set) + "\n" + authentication_context_id + "\n").encode()
        if len(request) > self._limit:
            raise ValueError("host administration request exceeds transport bound")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(30)
            client.connect(str(self._socket_path))
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            response = bytearray()
            while len(response) <= self._limit:
                chunk = client.recv(min(65_536, self._limit + 1 - len(response)))
                if not chunk:
                    break
                response.extend(chunk)
        if len(response) > self._limit:
            raise ValueError("host administration response exceeds transport bound")
        value = loads_document(bytes(response).decode("utf-8"))
        if not isinstance(value, HostAdministrationReceipt):
            raise TypeError("host administration broker returned an unexpected contract")
        return value
