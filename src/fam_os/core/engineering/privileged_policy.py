"""Core admission gates and ports for privileged and secret-bearing effects."""

from datetime import datetime
from typing import Protocol

from fam_os.core.engineering.authority import EngineeringAuthority
from fam_os.core.engineering.grants import (
    EngineeringAuthorityGrant,
    SecretExposurePolicy,
)
from fam_os.core.engineering.privileged import (
    HostAdministrationChangeSet, HostAdministrationReceipt,
    SecretUseAuthorization, SecretUseLevel,
)


class InteractiveOwnerAuthenticator(Protocol):
    def verify(self, owner_id: str, authentication_context_id: str) -> bool: ...


class HostAdministrationBroker(Protocol):
    def apply(
        self,
        change_set: HostAdministrationChangeSet,
        authentication_context_id: str,
    ) -> HostAdministrationReceipt: ...


class SecretProvider(Protocol):
    def use_opaque(self, secret_ref: str, consumer_id: str) -> str: ...

    def transform_redacted(self, secret_ref: str, consumer_id: str) -> tuple[str, str]: ...

    def disclose(self, secret_ref: str, consumer_id: str) -> str: ...


class HostAdministrationGate:
    def __init__(self, authenticator: InteractiveOwnerAuthenticator) -> None:
        self._authenticator = authenticator

    def authorize(
        self,
        change_set: HostAdministrationChangeSet,
        grant: EngineeringAuthorityGrant,
        authentication_context_id: str,
        *,
        instant: datetime,
    ) -> None:
        if not grant.active_at(instant) or grant.grant_id != change_set.grant_id:
            raise PermissionError("host administration grant is inactive or mismatched")
        if grant.owner_id != change_set.owner_id:
            raise PermissionError("host administration owner is mismatched")
        if EngineeringAuthority.HOST_ADMIN not in grant.authorities:
            raise PermissionError("host administration authority was not granted")
        if (change_set.global_install or change_set.host_toolchain_change) and EngineeringAuthority.GLOBAL_INSTALL not in grant.authorities:
            raise PermissionError("global installation authority was not granted")
        if not self._authenticator.verify(change_set.owner_id, authentication_context_id):
            raise PermissionError("interactive owner authentication failed")


class SecretUseGate:
    def authorize(
        self,
        authorization: SecretUseAuthorization,
        grant: EngineeringAuthorityGrant,
        *,
        principal_id: str,
        consumer_id: str,
        instant: datetime,
    ) -> None:
        if not grant.active_at(instant) or grant.grant_id != authorization.grant_id:
            raise PermissionError("secret-use grant is inactive or mismatched")
        if EngineeringAuthority.SECRET_USE not in grant.authorities:
            raise PermissionError("secret-use authority was not granted")
        if authorization.secret_ref not in grant.scope.secret_refs:
            raise PermissionError("secret reference is outside the grant")
        if authorization.principal_id != principal_id or grant.principal_id != principal_id:
            raise PermissionError("secret-use principal is mismatched")
        if authorization.approved_consumer_id != consumer_id:
            raise PermissionError("secret consumer is mismatched")
        if not authorization.issued_at <= instant < authorization.expires_at:
            raise PermissionError("secret-use authorization is expired")
        permitted_levels = {
            SecretExposurePolicy.NONE: set(),
            SecretExposurePolicy.NAMED_REFERENCES: {SecretUseLevel.OPAQUE_INJECTION},
            SecretExposurePolicy.PLAINTEXT_TO_APPROVED_TOOL: {SecretUseLevel.OPAQUE_INJECTION},
            SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION: {SecretUseLevel.OPAQUE_INJECTION},
            SecretExposurePolicy.REDACTED_TRANSFORMATION: {
                SecretUseLevel.OPAQUE_INJECTION,
                SecretUseLevel.REDACTED_TRANSFORMATION,
            },
            SecretExposurePolicy.DIRECT_MODEL_VISIBLE_DISCLOSURE: set(SecretUseLevel),
        }[grant.secret_exposure]
        if authorization.level not in permitted_levels:
            raise PermissionError("secret-use level exceeds the explicit grant")
        if authorization.level is SecretUseLevel.DIRECT_MODEL_DISCLOSURE and authorization.direct_disclosure_consequences_sha256 is None:
            raise PermissionError("direct model disclosure lacks exact consequence approval")
