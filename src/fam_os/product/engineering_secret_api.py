"""Authenticated owner lifecycle for encrypted engineering secret references."""

from datetime import datetime, timezone
import hashlib


class ProductEngineeringSecretApi:
    def __init__(
        self, owner_id, repository, authentication, clock=None, *,
        lifecycle, environments,
    ) -> None:
        if lifecycle is None or environments is None:
            raise ValueError("engineering secret lifecycle is required")
        self._owner_id = owner_id
        self._repository = repository
        self._authentication = authentication
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lifecycle = lifecycle
        self._environments = environments

    def provision(self, document, session_id):
        expected = {
            "owner_id", "secret_ref", "tool_key", "consumer_id", "value",
            "authentication_context_id", "confirmed",
        }
        _exact(document, expected)
        self._owner(document)
        digest = engineering_secret_operation_digest(
            "provision", document["secret_ref"], document["tool_key"],
            document["consumer_id"], document["value"],
        )
        self._consume(document, session_id, "engineering-secret-provision", digest)
        return self._repository.provision(
            document["secret_ref"], document["tool_key"],
            document["consumer_id"], document["value"], self._clock(),
        )

    def rotate(self, document, session_id):
        _exact(document, {
            "owner_id", "secret_ref", "value",
            "authentication_context_id", "confirmed",
        })
        self._owner(document)
        digest = engineering_secret_operation_digest(
            "rotate", document["secret_ref"], "", "", document["value"],
        )
        self._consume(document, session_id, "engineering-secret-rotate", digest)
        with self._lifecycle.locked():
            self._lifecycle.drain_reference(
                document["secret_ref"], self._owner_id, self._environments,
            )
            return self._repository.rotate(
                document["secret_ref"], document["value"], self._clock(),
            )

    def delete(self, document, session_id):
        _exact(document, {
            "owner_id", "secret_ref", "authentication_context_id", "confirmed",
        })
        self._owner(document)
        digest = engineering_secret_operation_digest(
            "delete", document["secret_ref"], "", "", "",
        )
        self._consume(document, session_id, "engineering-secret-delete", digest)
        with self._lifecycle.locked():
            self._lifecycle.drain_reference(
                document["secret_ref"], self._owner_id, self._environments,
            )
            return self._repository.delete(
                document["secret_ref"], self._clock(),
            )

    def inspect(self, secret_ref):
        return self._repository.metadata(_text(secret_ref, "secret_ref"))

    def list(self):
        return self._repository.list_metadata()

    def audit(self, secret_ref):
        secret_ref = _text(secret_ref, "secret_ref")
        self._repository.metadata(secret_ref)
        return {"secret_ref": secret_ref, "events": self._repository.audit(secret_ref)}

    def _owner(self, document):
        if document["confirmed"] is not True:
            raise PermissionError("engineering secret mutation requires confirmation")
        if _text(document["owner_id"], "owner_id") != self._owner_id:
            raise PermissionError("engineering secret owner is invalid")

    def _consume(self, document, session_id, purpose, digest):
        context_id = _text(document["authentication_context_id"], "context_id")
        if not self._authentication.consume(
            context_id, self._owner_id, purpose, digest,
            transport_session_id=session_id,
        ):
            raise PermissionError("engineering secret authentication is invalid")


def engineering_secret_operation_digest(action, secret_ref, tool_key, consumer_id, value):
    if action not in {"provision", "rotate", "delete"}:
        raise ValueError("engineering secret operation is invalid")
    _text(secret_ref, "secret_ref")
    if action == "provision":
        _text(tool_key, "tool_key"); _text(consumer_id, "consumer_id"); _value(value)
    elif action == "rotate":
        if tool_key or consumer_id: raise ValueError("rotate metadata must be empty")
        _value(value)
    elif tool_key or consumer_id or value:
        raise ValueError("delete payload must be empty")
    values = action, secret_ref, tool_key, consumer_id, value
    return hashlib.sha256("\0".join(values).encode()).hexdigest()


def _exact(document, expected):
    if not isinstance(document, dict) or set(document) != expected:
        raise ValueError("engineering secret fields must match exactly")


def _text(value, name, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()) or "\0" in value:
        raise ValueError(f"engineering {name} is invalid")
    return value


def _value(value):
    if not isinstance(value, str) or not value.strip() or "\0" in value or len(value.encode()) > 65_536:
        raise ValueError("engineering secret value is invalid")
    return value
