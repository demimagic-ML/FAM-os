import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from fam_os.adapters.linux.accessibility.types import (
    ProviderAccessibleAction, ProviderAccessibleNode,
)
from fam_os.adapters.linux.screen_input.types import (
    ProviderScreenFrame, ProviderWindowState,
)
from fam_os.applications import (
    ActionConfirmation, ActionPreparationRequest, ConfirmationDecision,
    ObservationRequest,
)
from fam_os.applications.registry import ApplicationCapabilityRegistry
from fam_os.product.composition.fallbacks import ProductFallbacks


NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


class ProductFallbackConfigurationTests(unittest.TestCase):
    def test_absent_configuration_keeps_both_mechanisms_disabled(self):
        registry = ApplicationCapabilityRegistry()
        manager = ProductFallbacks.from_file(registry, Path("/missing/fallbacks.json"))
        manager.start()
        self.assertEqual((), registry.entries())
        self.assertEqual(
            ["disabled", "disabled"],
            [item["issue_code"] for item in manager.status()],
        )

    def test_configuration_is_private_strict_and_requires_privacy_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fallbacks.json"
            document = _document()
            path.write_text(json.dumps(document), encoding="utf-8")
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                ProductFallbacks.from_file(ApplicationCapabilityRegistry(), path)
            os.chmod(path, 0o600)
            document["unexpected"] = True
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                ProductFallbacks.from_file(ApplicationCapabilityRegistry(), path)
            document = _document(accessibility=True)
            document["accessibility"]["privacy_acknowledged"] = False
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(PermissionError):
                ProductFallbacks.from_file(ApplicationCapabilityRegistry(), path)

    def test_versioned_schema_rejects_unknown_fields(self):
        schema = json.loads(Path(
            "schemas/v1alpha1/fam.product.fallbacks-config.schema.json"
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(_document(accessibility=True, screen=True))
        invalid = _document()
        invalid["accessibility"]["automatic_discovery"] = True
        with self.assertRaises(ValidationError):
            validator.validate(invalid)


class ProductFallbackLifecycleTests(unittest.TestCase):
    def test_explicit_targets_register_and_execute_bounded_transports(self):
        with tempfile.TemporaryDirectory() as directory:
            manager, registry, accessibility, screen = _manager(
                Path(directory), _document(accessibility=True, screen=True),
            )
            manager.start()
            capabilities = {item.capability_id for item in registry.entries()}
            self.assertEqual({
                "linux.accessibility.observe_tree",
                "linux.accessibility.invoke_action",
                "linux.screen.observe_active_window",
                "linux.input.control_active_window",
            }, capabilities)
            statuses = {item["mechanism"]: item for item in manager.status()}
            self.assertTrue(statuses["accessibility"]["actions_active"])
            self.assertTrue(statuses["screen_input"]["actions_active"])
            self._exercise_accessibility(manager, accessibility)
            self._exercise_screen(manager, screen)
            manager.close()
            self.assertEqual((), registry.entries())

    def test_observation_only_and_unavailable_input_never_register_action_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            document = _document(accessibility=True, screen=True)
            document["accessibility"]["actions_enabled"] = False
            screen = FakeScreenProvider(input_available=False)
            manager, registry, _, _ = _manager(Path(directory), document, screen=screen)
            manager.start()
            capabilities = {item.capability_id for item in registry.entries()}
            self.assertNotIn("linux.accessibility.invoke_action", capabilities)
            self.assertNotIn("linux.input.control_active_window", capabilities)
            self.assertIn("linux.screen.observe_active_window", capabilities)
            screen_status = manager.status()[1]
            self.assertEqual("input_unavailable", screen_status["issue_code"])
            self.assertFalse(screen_status["actions_active"])

    def _exercise_accessibility(self, manager, provider):
        transport = manager.transport("atspi.editor")
        observed = transport.observe(ObservationRequest(
            "observe-atspi", "atspi-editor", "linux.accessibility.observe_tree",
            "grant-atspi", {}, "process:100",
        ))
        reference = dict(observed.payload["nodes"][0]["reference"])
        proposal = transport.prepare_action(ActionPreparationRequest(
            "prepare-atspi", "atspi-editor", "linux.accessibility.invoke_action",
            "grant-atspi", "Click the exact accessible object.",
            {"reference": reference, "action_name": "click"}, "process:100",
        ))
        result = transport.execute_action(proposal, _confirmation(proposal.proposal_id))
        self.assertTrue(result.verified)
        self.assertEqual(("root", 0), provider.performed)

    def _exercise_screen(self, manager, provider):
        transport = manager.transport("screen.editor")
        observed = transport.observe(ObservationRequest(
            "observe-screen", "screen-editor", "linux.screen.observe_active_window",
            "grant-screen", {}, "window:0x2a",
        ))
        proposal = transport.prepare_action(ActionPreparationRequest(
            "prepare-screen", "screen-editor", "linux.input.control_active_window",
            "grant-screen", "Click inside the exact active window.", {
                "expected_scene_id": observed.revision,
                "instruction": {
                    "kind": "pointer_click",
                    "point": {"x_millionths": 500_000, "y_millionths": 500_000},
                },
            }, "window:0x2a",
        ))
        result = transport.execute_action(proposal, _confirmation(proposal.proposal_id))
        self.assertTrue(result.verified)
        self.assertEqual(1, len(provider.injected))


class FakeAccessibilityProvider:
    def __init__(self):
        self.node = ProviderAccessibleNode(
            100, "push button", "Save", "Save document", ("enabled",),
            (ProviderAccessibleAction(0, "click"),), None, False, 0, False,
        )
        self.performed = None

    def available(self):
        return True

    def roots(self):
        return ("root",)

    def read(self, handle, maximum_text_characters, include_text=False):
        return self.node if include_text else replace(self.node, text=None)

    def child(self, handle, index):
        return None

    def perform_action(self, handle, action_index):
        self.performed = (handle, action_index)
        return True


class FakeScreenProvider:
    def __init__(self, input_available=True):
        self.state = ProviderWindowState("0x2a", 200, 0, 0, 800, 600, True)
        self._input_available = input_available
        self.injected = []

    def capture_available(self):
        return True

    def input_available(self):
        return self._input_available

    def inspect(self, target):
        return self.state

    def capture(self, target, maximum_source_pixels, maximum_pixels, maximum_bytes):
        return ProviderScreenFrame(
            self.state, 800, 600, b"\x89PNG\r\n\x1a\nbounded",
        )

    def inject(self, target, action):
        self.injected.append(action)
        return True


def _manager(root: Path, document: dict, screen=None):
    path = root / "fallbacks.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    os.chmod(path, 0o600)
    registry = ApplicationCapabilityRegistry()
    accessibility = FakeAccessibilityProvider()
    screen = screen or FakeScreenProvider()
    manager = ProductFallbacks.from_file(
        registry, path, lambda: accessibility, lambda: screen,
    )
    return manager, registry, accessibility, screen


def _document(accessibility=False, screen=False):
    return {
        "contract_version": "fam.product.fallbacks/v1alpha1",
        "accessibility": {
            "enabled": accessibility, "privacy_acknowledged": accessibility,
            "include_text": False, "actions_enabled": accessibility,
            "allowed_actions": ["click"],
            "targets": [{
                "connector_id": "atspi.editor", "instance_id": "atspi-editor",
                "process_id": 100,
            }] if accessibility else [],
        },
        "screen_input": {
            "enabled": screen, "privacy_acknowledged": screen,
            "actions_enabled": screen, "allowed_kinds": ["pointer_click"],
            "allowed_keys": ["Control_L"],
            "targets": [{
                "connector_id": "screen.editor", "instance_id": "screen-editor",
                "application_id": "org.example.Editor", "process_id": 200,
                "window_id": "0x2a",
            }] if screen else [],
        },
    }


def _confirmation(proposal_id: str) -> ActionConfirmation:
    return ActionConfirmation(
        "confirmation-1", proposal_id, "grant-1", ConfirmationDecision.APPROVED,
        "local-owner", NOW,
    )


if __name__ == "__main__":
    unittest.main()
