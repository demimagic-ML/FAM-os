import unittest
from datetime import datetime, timedelta, timezone

from fam_os.core.admission import (
    InMemoryRequestAuthorityRegistry, InMemoryRequestReplayRegistry,
    RequestAdmissionService, RequestAuthorityGrant, RequestIdentity,
)
from fam_os.core.contracts import ResultStatus, TaskResult
from fam_os.core.ingress import (
    CoreIngressRequest, InMemoryIngressCapabilityRegistry, IngressCapability,
    LifecycleCoreIngressGateway,
)


NOW = datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc)


class CoreIngressGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.identity = RequestIdentity("user-1", "session-1", "authority-1")
        self.authorities = InMemoryRequestAuthorityRegistry((RequestAuthorityGrant(
            "authority-1", "user-1", "session-1", ("fam.ask",),
            NOW - timedelta(minutes=1), NOW + timedelta(hours=1),
        ),))
        self.executor = Executor()
        admission = RequestAdmissionService(
            self.authorities, InMemoryRequestReplayRegistry(),
            clock=lambda: NOW, admission_id_factory=lambda: "admission-1",
            error_id_factory=lambda: "admission-error",
        )
        self.gateway = LifecycleCoreIngressGateway(
            _capabilities(), self.authorities, admission, self.executor,
            clock=lambda: NOW, error_id_factory=lambda: "ingress-error",
        )

    async def test_visibility_and_invocation_reenter_core_admission(self):
        visible = await self.gateway.visible_capabilities(self.identity)
        self.assertEqual(("fam.ask",), tuple(item.capability_id for item in visible))
        result = await self.gateway.invoke(
            self.identity, CoreIngressRequest("request-1", "fam.ask", {"prompt": "hi"})
        )
        self.assertEqual(ResultStatus.VERIFIED, result.status)
        admitted, parameters = self.executor.calls[-1]
        self.assertEqual(("fam.ask",), admitted.permission.authorized_capabilities)
        self.assertEqual("hi", parameters["prompt"])

    async def test_invalid_hidden_and_replayed_requests_never_bypass_admission(self):
        invalid = await self.gateway.invoke(
            self.identity, CoreIngressRequest("invalid-1", "fam.ask", {})
        )
        self.assertEqual("ingress.input_invalid", invalid.failure.code)
        hidden = await self.gateway.invoke(
            self.identity,
            CoreIngressRequest("hidden-1", "fam.admin", {"prompt": "x"}),
        )
        self.assertEqual("admission.capability_denied", hidden.failure.code)
        self.assertEqual([], self.executor.calls)

        request = CoreIngressRequest("replay-1", "fam.ask", {"prompt": "x"})
        self.assertEqual(ResultStatus.VERIFIED, (await self.gateway.invoke(self.identity, request)).status)
        replay = await self.gateway.invoke(self.identity, request)
        self.assertEqual("admission.request_replayed", replay.failure.code)

    async def test_required_verification_withholds_unverified_executor_content(self):
        self.executor.unverified = True
        result = await self.gateway.invoke(
            self.identity, CoreIngressRequest("request-2", "fam.ask", {"prompt": "hi"})
        )
        self.assertEqual(ResultStatus.WITHHELD, result.status)
        self.assertIsNone(result.content)
        self.assertEqual("ingress.verification_required", result.failure.code)

    async def test_expired_or_wrong_identity_sees_no_capabilities(self):
        wrong = RequestIdentity("other", "session-1", "authority-1")
        self.assertEqual((), await self.gateway.visible_capabilities(wrong))
        self.gateway.clock = lambda: NOW + timedelta(days=1)
        self.assertEqual((), await self.gateway.visible_capabilities(self.identity))

    async def test_executor_exception_is_content_free_safe_failure(self):
        self.executor.fail = True
        result = await self.gateway.invoke(
            self.identity, CoreIngressRequest("request-3", "fam.ask", {"prompt": "hi"})
        )
        self.assertEqual("ingress.execution_failed", result.failure.code)
        self.assertNotIn("private executor detail", result.reason)


class Executor:
    def __init__(self):
        self.calls = []
        self.unverified = False
        self.fail = False

    async def execute(self, admitted, parameters):
        self.calls.append((admitted, parameters))
        if self.fail:
            raise RuntimeError("private executor detail")
        if self.unverified:
            return TaskResult(
                admitted.request.request_id, ResultStatus.COMPLETED, "unverified content"
            )
        return TaskResult(
            admitted.request.request_id, ResultStatus.VERIFIED, "verified content",
            verified=True, evidence_ids=("evidence-1",),
        )


def _capabilities():
    schema = {
        "type": "object", "properties": {"prompt": {"type": "string"}},
        "required": ["prompt"], "additionalProperties": False,
    }
    output = {"type": "object"}
    return InMemoryIngressCapabilityRegistry((
        IngressCapability("fam.ask", "Ask FAM", "Submit an admitted FAM task", schema, output),
        IngressCapability("fam.admin", "Admin FAM", "Unavailable admin task", schema, output),
    ))


if __name__ == "__main__":
    unittest.main()
