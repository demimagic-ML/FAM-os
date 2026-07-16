"""Application Fabric dispatch port behind the local wire transport."""

from typing import Protocol

from fam_os.applications.transport.session import LocalTransportSession
from fam_os.applications.transport.wire import LocalMessage


class LocalMessageDispatcher(Protocol):
    def dispatch(
        self, session: LocalTransportSession, message: LocalMessage
    ) -> LocalMessage | None: ...

    def disconnected(
        self, session: LocalTransportSession, pending_request_ids: tuple[str, ...]
    ) -> None: ...
