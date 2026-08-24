import unittest
from types import SimpleNamespace

from fam_os.core.contracts import ResultKind, ResultStatus
from fam_os.product.composition.mcp_ingress_executor import (
    ProductionMcpTaskExecutor,
)
from fam_os.shell import ShellResult, ShellRunState, ShellSessionSnapshot


class ProductionMcpTaskExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_immediate_firewall_result_is_returned_without_snapshot_lookup(self):
        gateway = _ImmediateGateway()
        executor = ProductionMcpTaskExecutor(gateway)
        admitted = SimpleNamespace(
            request=SimpleNamespace(
                request_id="request-1", required_capabilities=("fam.ask",),
            ),
            permission=SimpleNamespace(
                principal_id="principal-1", session_id="session-1",
            ),
        )

        result = await executor.execute(admitted, {"prompt": "Delete a file."})

        self.assertIs(ResultStatus.WITHHELD, result.status)
        self.assertEqual("mcp.task.withheld", result.failure.code)
        self.assertEqual(0, gateway.snapshot_calls)


class _ImmediateGateway:
    snapshot_calls = 0

    def ask_as(self, command, principal_id, session_id):
        return ShellSessionSnapshot(
            "admission-request", command.request_id, 1,
            ShellRunState.TERMINAL,
            result=ShellResult(
                command.request_id, ResultStatus.WITHHELD, None,
                "No authorized action capability is available.",
                result_kind=ResultKind.CAPABILITY_UNAVAILABLE,
            ),
        )

    def snapshot(self, session_id):
        self.snapshot_calls += 1
        raise AssertionError("an immediate terminal result must not be reloaded")

    def cancel(self, command):
        raise AssertionError("an immediate terminal result must not be cancelled")


if __name__ == "__main__":
    unittest.main()
