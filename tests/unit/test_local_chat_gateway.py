import unittest

from fam_os.core.contracts import ResultStatus
from fam_os.core.ingress.local_chat_gateway import LocalInferenceShellGateway
from fam_os.shell import ShellAskCommand, ShellRunState


class _Response:
    content = "Hello from the local model."


class _Runtime:
    def __init__(self, fails=False):
        self.fails = fails
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        if self.fails:
            raise RuntimeError("provider details must not escape")
        return _Response()

    def unload(self, model_ref):
        return None

    def loaded_models(self):
        return ()


class LocalChatGatewayTests(unittest.TestCase):
    def test_accepts_then_returns_unverified_local_result(self) -> None:
        runtime = _Runtime()
        gateway = LocalInferenceShellGateway(runtime, "model:local")
        accepted = gateway.ask(ShellAskCommand("request", "Say hello"))
        result = gateway.snapshot(accepted.session_id)
        self.assertEqual(result.state, ShellRunState.TERMINAL)
        self.assertEqual(result.result.status, ResultStatus.COMPLETED)
        self.assertFalse(result.result.verified)
        self.assertEqual(runtime.requests[0].model_ref, "model:local")

    def test_provider_failure_is_content_safe(self) -> None:
        gateway = LocalInferenceShellGateway(_Runtime(True), "model:local")
        accepted = gateway.ask(ShellAskCommand("request", "Say hello"))
        result = gateway.snapshot(accepted.session_id)
        self.assertEqual(result.result.status, ResultStatus.FAILED)
        self.assertEqual(result.result.reason, "Local inference is unavailable")

    def test_rejects_context_capabilities_and_verification_claims(self) -> None:
        gateway = LocalInferenceShellGateway(_Runtime(), "model:local")
        with self.assertRaisesRegex(ValueError, "unverified"):
            gateway.ask(ShellAskCommand("request", "hello", verification_required=True))


if __name__ == "__main__":
    unittest.main()
