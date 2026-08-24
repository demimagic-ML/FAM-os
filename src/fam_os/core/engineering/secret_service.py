"""One-use service for opaque, redacted, or explicitly disclosed secrets."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from fam_os.core.engineering.grants import EngineeringAuthorityGrant
from fam_os.core.engineering.privileged import (
    SecretUseAuthorization, SecretUseLevel, SecretUseReceipt,
)
from fam_os.core.engineering.privileged_policy import SecretProvider, SecretUseGate


@dataclass(frozen=True, slots=True)
class SecretUseOutcome:
    receipt: SecretUseReceipt
    model_visible_value: str | None
    transformed_output: str | None


class EngineeringSecretService:
    def __init__(self, provider: SecretProvider, gate=None) -> None:
        self._provider = provider
        self._gate = gate or SecretUseGate()
        self._uses: dict[str, int] = {}

    def use(
        self,
        authorization: SecretUseAuthorization,
        grant: EngineeringAuthorityGrant,
        *,
        principal_id: str,
        consumer_id: str,
        instant: datetime,
    ) -> SecretUseOutcome:
        self._gate.authorize(
            authorization, grant, principal_id=principal_id,
            consumer_id=consumer_id, instant=instant,
        )
        used = self._uses.get(authorization.authorization_id, 0)
        if used >= authorization.maximum_uses:
            raise PermissionError("secret-use authorization is consumed")
        model_value = transformed = redaction_id = None
        if authorization.level is SecretUseLevel.OPAQUE_INJECTION:
            output = self._provider.use_opaque(authorization.secret_ref, consumer_id)
        elif authorization.level is SecretUseLevel.REDACTED_TRANSFORMATION:
            output, redaction_id = self._provider.transform_redacted(
                authorization.secret_ref, consumer_id,
            )
            transformed = output
        else:
            output = self._provider.disclose(authorization.secret_ref, consumer_id)
            model_value = output
        self._uses[authorization.authorization_id] = used + 1
        receipt = SecretUseReceipt(
            f"secret-receipt-{uuid4().hex}", authorization.authorization_id,
            authorization.secret_ref, consumer_id, authorization.level, instant,
            hashlib.sha256(output.encode("utf-8")).hexdigest(), redaction_id,
        )
        return SecretUseOutcome(receipt, model_value, transformed)
