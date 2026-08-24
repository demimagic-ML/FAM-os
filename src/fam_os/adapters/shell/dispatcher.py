"""Content-safe server dispatch from Shell wire requests to a Core gateway."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from fam_os.adapters.shell.memory_dispatch import (
    MemoryServiceUnavailable,
    dispatch_memory,
)
from fam_os.adapters.shell.adaptation_dispatch import (
    AdaptationServiceUnavailable,
    dispatch_adaptation,
)
from fam_os.adapters.shell.peer_dispatch import PeerServiceUnavailable, dispatch_peer
from fam_os.adapters.shell.engineering_authority_dispatch import (
    EngineeringAuthorityUnavailable,
    dispatch_engineering_authority,
)
from fam_os.adapters.shell.integration_environment_dispatch import (
    IntegrationEnvironmentUnavailable,
    dispatch_integration_environment,
)
from fam_os.adapters.shell.engineering_secret_dispatch import (
    EngineeringSecretUnavailable, dispatch_engineering_secret,
)
from fam_os.adapters.shell.engineering_loop_dispatch import (
    EngineeringLoopUnavailable, dispatch_engineering_loop,
)
from fam_os.adapters.shell.natural_engineering import NaturalEngineeringShellAdapter
from fam_os.core.production.grounding_port import GroundedRetrievalUnavailable
from fam_os.shell.contracts import ShellSessionSnapshot
from fam_os.shell.memory_contracts import ShellMemoryResponse
from fam_os.shell.adaptation_contracts import ShellAdaptationResponse
from fam_os.shell.ports import (
    ShellAdaptationGateway,
    ShellCoreGateway,
    ShellMemoryGateway,
)
from fam_os.shell.wire import (
    ShellWireKind,
    adaptation_response_message,
    decode_request,
    error_message,
    memory_response_message,
    snapshot_message,
    engineering_response_message,
    integration_environment_response_message,
    engineering_secret_response_message,
    engineering_loop_response_message,
)


def _identifier() -> str:
    return str(uuid4())


@dataclass(slots=True)
class ShellRequestDispatcher:
    gateway: ShellCoreGateway
    memory: ShellMemoryGateway | None = None
    message_id_factory: Callable[[], str] = _identifier
    adaptation: ShellAdaptationGateway | None = None
    peer: object | None = None
    engineering_authority: object | None = None
    integration_environment: object | None = None
    engineering_secrets: object | None = None
    engineering_loop: object | None = None
    natural_engineering: object | None = None

    def dispatch(self, message):
        try:
            command = decode_request(message)
        except Exception:
            return self._error(message, "shell.request_invalid")
        try:
            response = self._invoke(message.kind, command)
        except MemoryServiceUnavailable:
            return self._error(message, "shell.memory_unavailable")
        except AdaptationServiceUnavailable:
            return self._error(message, "shell.adaptation_unavailable")
        except PeerServiceUnavailable:
            return self._error(message, "shell.peer_unavailable")
        except EngineeringAuthorityUnavailable:
            return self._error(message, "shell.engineering_unavailable")
        except IntegrationEnvironmentUnavailable:
            return self._error(message, "shell.integration_environment_unavailable")
        except EngineeringSecretUnavailable:
            return self._error(message, "shell.engineering_secret_unavailable")
        except EngineeringLoopUnavailable:
            return self._error(message, "shell.engineering_loop_unavailable")
        except KeyError:
            code = _scoped_error(message.kind, "not_found")
            return self._error(message, code)
        except PermissionError:
            code = _scoped_error(message.kind, "denied")
            return self._error(message, code)
        except GroundedRetrievalUnavailable:
            return self._error(message, "shell.grounding_unavailable")
        except ValueError:
            code = _scoped_error(message.kind, "conflict")
            return self._error(message, code)
        except Exception:
            code = _scoped_error(message.kind, "unavailable")
            return self._error(message, code)
        if _is_memory(message.kind):
            return self._memory_response(message, command, response)
        if _is_adaptation(message.kind):
            return self._adaptation_response(message, command, response)
        if _is_peer(message.kind):
            return self._peer_response(message, command, response)
        if _is_engineering_authority(message.kind):
            return self._engineering_response(message, command, response)
        if _is_integration_environment(message.kind):
            return self._integration_environment_response(message, command, response)
        if _is_engineering_secret(message.kind):
            return self._engineering_secret_response(message, command, response)
        if _is_engineering_loop(message.kind):
            return self._engineering_loop_response(message, command, response)
        if not isinstance(response, ShellSessionSnapshot):
            return self._error(message, "shell.response_invalid")
        if not _identity_matches(message.kind, command, response):
            return self._error(message, "shell.response_invalid")
        return snapshot_message(
            self.message_id_factory(), message.message_id, response
        )

    def _invoke(self, kind, command):
        natural = (
            None if self.natural_engineering is None
            else NaturalEngineeringShellAdapter(self.natural_engineering)
        )
        if (
            natural is not None
            and kind is ShellWireKind.ASK
            and natural.handles_ask(command)
        ):
            return natural.propose(command)
        if (
            natural is not None
            and kind is ShellWireKind.DECIDE
            and natural.handles_session(command.session_id)
        ):
            return natural.decide(command)
        if (
            natural is not None
            and kind is ShellWireKind.SNAPSHOT_QUERY
            and natural.handles_session(command.session_id)
        ):
            return natural.snapshot(command)
        if _is_memory(kind):
            return dispatch_memory(self.memory, command)
        if _is_adaptation(kind):
            return dispatch_adaptation(self.adaptation, command)
        if _is_peer(kind):
            return dispatch_peer(self.peer, command)
        if _is_engineering_authority(kind):
            return dispatch_engineering_authority(self.engineering_authority, command)
        if _is_integration_environment(kind):
            return dispatch_integration_environment(self.integration_environment, command)
        if _is_engineering_secret(kind):
            return dispatch_engineering_secret(self.engineering_secrets, command)
        if _is_engineering_loop(kind):
            return dispatch_engineering_loop(self.engineering_loop, command)
        if kind is ShellWireKind.ASK:
            return self.gateway.ask(command)
        if kind is ShellWireKind.VERIFIED_ASK:
            return self.gateway.ask_verified(command)
        if kind is ShellWireKind.SNAPSHOT_QUERY:
            return self.gateway.snapshot(command.session_id)
        if kind is ShellWireKind.DECIDE:
            return self.gateway.decide(command)
        if kind is ShellWireKind.CANCEL:
            return self.gateway.cancel(command)
        raise ValueError("unsupported shell request")

    def _memory_response(self, message, command, response):
        if not isinstance(response, ShellMemoryResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return memory_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _adaptation_response(self, message, command, response):
        if not isinstance(response, ShellAdaptationResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return adaptation_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _peer_response(self, message, command, response):
        from fam_os.shell.peer_contracts import ShellPeerResponse
        from fam_os.shell.wire import peer_response_message
        if not isinstance(response, ShellPeerResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return peer_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _engineering_response(self, message, command, response):
        from fam_os.shell.engineering_authority_contracts import (
            ShellEngineeringAuthorityResponse,
        )
        if not isinstance(response, ShellEngineeringAuthorityResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return engineering_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _integration_environment_response(self, message, command, response):
        from fam_os.shell import ShellIntegrationEnvironmentResponse
        if not isinstance(response, ShellIntegrationEnvironmentResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return integration_environment_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _engineering_secret_response(self, message, command, response):
        from fam_os.shell import ShellEngineeringSecretResponse
        if not isinstance(response, ShellEngineeringSecretResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return engineering_secret_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _engineering_loop_response(self, message, command, response):
        from fam_os.shell import ShellEngineeringLoopResponse
        if not isinstance(response, ShellEngineeringLoopResponse):
            return self._error(message, "shell.response_invalid")
        if response.request_id != command.request_id:
            return self._error(message, "shell.response_invalid")
        return engineering_loop_response_message(
            self.message_id_factory(), message.message_id, response,
        )

    def _error(self, message, code):
        return error_message(
            self.message_id_factory(), message.message_id, code
        )


def _identity_matches(kind, command, snapshot) -> bool:
    if kind is ShellWireKind.ASK:
        return snapshot.request_id == command.request_id
    if kind is ShellWireKind.VERIFIED_ASK:
        return snapshot.request_id == command.command.request_id
    return snapshot.session_id == command.session_id


def _is_memory(kind) -> bool:
    return kind in {
        ShellWireKind.MEMORY_QUERY,
        ShellWireKind.MEMORY_CORRECT,
        ShellWireKind.MEMORY_EXPIRE,
        ShellWireKind.MEMORY_DELETE,
    }


def _is_adaptation(kind) -> bool:
    return kind in {
        ShellWireKind.ADAPTATION_QUERY,
        ShellWireKind.ADAPTATION_CONTROL,
    }


def _is_peer(kind) -> bool:
    return kind in {
        ShellWireKind.PEER_QUERY,
        ShellWireKind.PEER_PROBE,
        ShellWireKind.PEER_CONTROL,
        ShellWireKind.PEER_CONTEXT,
    }


def _is_engineering_authority(kind) -> bool:
    return kind in {
        ShellWireKind.ENGINEERING_CONTEXT,
        ShellWireKind.ENGINEERING_ACTIVATE,
        ShellWireKind.ENGINEERING_QUERY,
        ShellWireKind.ENGINEERING_REVOKE,
    }


def _is_integration_environment(kind) -> bool:
    return kind in {
        ShellWireKind.INTEGRATION_ENVIRONMENT_START,
        ShellWireKind.INTEGRATION_ENVIRONMENT_QUERY,
        ShellWireKind.INTEGRATION_ENVIRONMENT_CONTROL,
    }


def _is_engineering_secret(kind) -> bool:
    return kind in {
        ShellWireKind.ENGINEERING_SECRET_QUERY,
        ShellWireKind.ENGINEERING_SECRET_MUTATION,
    }


def _is_engineering_loop(kind) -> bool:
    return kind in {
        ShellWireKind.ENGINEERING_LOOP_START,
        ShellWireKind.ENGINEERING_LOOP_QUERY,
        ShellWireKind.ENGINEERING_LOOP_MUTATION,
        ShellWireKind.ENGINEERING_CANDIDATE_EDIT,
        ShellWireKind.ENGINEERING_CANDIDATE_VERIFY,
        ShellWireKind.ENGINEERING_CANDIDATE_REVERIFY,
        ShellWireKind.ENGINEERING_CHANGESET_PREVIEW,
        ShellWireKind.ENGINEERING_CHANGESET_APPLY,
        ShellWireKind.ENGINEERING_PUBLICATION,
        ShellWireKind.ENGINEERING_INCIDENT_ADVANCE,
    }


def _scoped_error(kind, suffix: str) -> str:
    if _is_memory(kind):
        return f"shell.memory_{suffix}"
    if _is_adaptation(kind):
        return f"shell.adaptation_{suffix}"
    if _is_peer(kind):
        return f"shell.peer_{suffix}"
    if _is_engineering_authority(kind):
        return f"shell.engineering_{suffix}"
    if _is_integration_environment(kind):
        return f"shell.integration_environment_{suffix}"
    if _is_engineering_secret(kind):
        return f"shell.engineering_secret_{suffix}"
    if _is_engineering_loop(kind):
        return f"shell.engineering_loop_{suffix}"
    return "shell.core_unavailable"
