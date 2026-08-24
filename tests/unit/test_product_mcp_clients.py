import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.mcp.client import McpOperationOutcome
from fam_os.adapters.mcp.mapping import map_discovery
from fam_os.adapters.mcp.types import (
    McpDiscoverySnapshot, McpServerInfo, McpTool,
)
from fam_os.applications import (
    ActionConfirmation, ActionPreparationRequest, ApplicationCapabilityRegistry,
    ConfirmationDecision, ObservationRequest,
)
from fam_os.product.composition.application_conditions import (
    LiveApplicationConditionVerifier,
)
from fam_os.product.composition.mcp_clients import ProductMcpClients


class ProductMcpClientTests(unittest.TestCase):
    def test_private_allowlist_starts_registers_routes_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mcp-clients.json"
            path.write_text(json.dumps(_configuration()))
            os.chmod(path, 0o600)
            registry = ApplicationCapabilityRegistry()
            workers = []

            def worker_factory(_configuration_value, policy):
                worker = _FakeWorker(policy)
                workers.append(worker)
                return worker

            with patch(
                "fam_os.product.composition.mcp_clients.McpClientWorker",
                side_effect=worker_factory,
            ):
                clients = ProductMcpClients.from_file(registry, path)
                clients.start()
                entry = registry.entries()[0]
                transport = clients.transport(entry.connector_id)
                self.assertIsNotNone(transport)
                parameters = transport.observation_parameters(
                    entry.capability_id, "find resident fabric", None,
                )
                self.assertEqual({"query": "find resident fabric"}, parameters)
                observed = transport.observe(ObservationRequest(
                    "observe-1", entry.instance_id, entry.capability_id, "grant-1",
                    parameters,
                ))
                self.assertEqual("observed", observed.status)
                clients.close()
            self.assertEqual((), registry.entries())
            self.assertTrue(workers[0].stopped)

    def test_mcp_action_assertion_does_not_satisfy_unknown_core_verifier(self):
        policy = _FakeWorker.policy()
        worker = _FakeWorker(policy)
        mapped = worker.start()
        action = next(
            item for item in mapped.bindings
            if item.entry.capability.kind.value == "action"
        )
        from fam_os.product.composition.mcp_transport import McpApplicationTransport
        transport = McpApplicationTransport(worker, mapped)
        proposal = transport.prepare_action(ActionPreparationRequest(
            "action-1", action.entry.instance_id, action.entry.capability_id,
            "grant-1", "Change through MCP", {"text": "new"},
        ))
        provider_result = transport.execute_action(proposal, ActionConfirmation(
            "confirmation-1", proposal.proposal_id, "grant-1",
            ConfirmationDecision.APPROVED, "local-owner", datetime.now(timezone.utc),
        ))
        evidence = LiveApplicationConditionVerifier(None).verify(
            proposal.postconditions[0], proposal, provider_result,
        )
        self.assertTrue(provider_result.verified)
        self.assertFalse(evidence.passed)

    def test_non_private_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mcp-clients.json"
            path.write_text(json.dumps(_configuration()))
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                ProductMcpClients.from_file(ApplicationCapabilityRegistry(), path)

    def test_required_observation_parameter_must_have_an_owner_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = _configuration()
            document["servers"][0]["tools"][0].pop("argument_bindings")
            path = Path(temporary) / "mcp-clients.json"
            path.write_text(json.dumps(document))
            os.chmod(path, 0o600)
            workers = []

            def worker_factory(_configuration_value, policy):
                worker = _FakeWorker(policy)
                workers.append(worker)
                return worker

            with patch(
                "fam_os.product.composition.mcp_clients.McpClientWorker",
                side_effect=worker_factory,
            ):
                clients = ProductMcpClients.from_file(
                    ApplicationCapabilityRegistry(), path,
                )
                with self.assertRaisesRegex(ValueError, "explicitly bound"):
                    clients.start()
            self.assertTrue(workers[0].stopped)

    def test_literal_observation_binding_is_schema_checked_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = _configuration()
            document["servers"][0]["tools"][0]["argument_bindings"].append({
                "parameter": "limit", "source": "literal", "value": 4,
            })
            path = Path(temporary) / "mcp-clients.json"
            path.write_text(json.dumps(document))
            os.chmod(path, 0o600)
            registry = ApplicationCapabilityRegistry()
            with patch(
                "fam_os.product.composition.mcp_clients.McpClientWorker",
                side_effect=lambda _configuration_value, policy: _FakeWorker(policy),
            ):
                clients = ProductMcpClients.from_file(registry, path)
                clients.start()
                try:
                    entry = next(
                        item for item in registry.entries()
                        if item.capability.display_name == "lookup"
                    )
                    parameters = clients.transport(
                        entry.connector_id,
                    ).observation_parameters(
                        entry.capability_id, "find fabric", None,
                    )
                    self.assertEqual(
                        {"query": "find fabric", "limit": 4}, parameters,
                    )
                finally:
                    clients.close()


class _FakeWorker:
    def __init__(self, policy):
        self._policy = policy
        self.stopped = False

    @staticmethod
    def policy():
        from fam_os.product.composition.mcp_clients import _definition
        return _definition(_configuration()["servers"][0]).policy

    def start(self):
        snapshot = McpDiscoverySnapshot(
            McpServerInfo("allowed-server", "1", "2025-11-25"), (),
            (
                McpTool("lookup", "Lookup", {
                    "type": "object", "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query"], "additionalProperties": False,
                }),
                McpTool("replace", "Replace", {
                    "type": "object", "properties": {"text": {"type": "string"}},
                    "required": ["text"], "additionalProperties": False,
                }),
            ),
        )
        return map_discovery(self._policy, snapshot, datetime.now(timezone.utc))

    def observe(self, capability_id, arguments):
        return McpOperationOutcome(capability_id, True, {"value": "answer"})

    def execute(self, capability_id, arguments):
        return McpOperationOutcome(capability_id, True, {"changed": True})

    def stop(self):
        self.stopped = True


def _configuration():
    return {
        "contract_version": "fam.product.mcp-clients/v1alpha1",
        "servers": [{
            "server_id": "allowed", "connector_id": "connector-mcp",
            "instance_id": "instance-mcp", "command": "/bin/true",
            "expected_server_name": "allowed-server",
            "application": {
                "application_id": "app.mcp", "display_name": "MCP application",
            },
            "tools": [
                {"tool_name": "lookup", "kind": "observation",
                 "required_authority": "observe", "argument_bindings": [{
                     "parameter": "query", "source": "prompt",
                 }]},
                {"tool_name": "replace", "kind": "action",
                 "required_authority": "modify", "reversibility": "irreversible",
                 "confirmation": "always", "postcondition_ids": ["mcp.changed"]},
            ],
        }],
    }


if __name__ == "__main__":
    unittest.main()
