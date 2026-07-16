import hashlib
import unittest
from datetime import datetime, timezone

from fam_os.adapters.linux.screen_input.bridge import ScreenInputBridge
from fam_os.adapters.linux.screen_input.catalog import build_screen_input_registration
from fam_os.adapters.linux.screen_input.policy import ScreenInputPolicy
from fam_os.adapters.linux.screen_input.types import ProviderScreenFrame, ProviderWindowState
from fam_os.applications import (
    ConfirmationPolicy, ConnectorTransportKind, RelativeScreenPoint,
    ScreenInputInstruction, ScreenInputKind, ScreenTarget,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)
PNG_A = b"\x89PNG\r\n\x1a\nscene-a"
PNG_B = b"\x89PNG\r\n\x1a\nscene-b"
TARGET = ScreenTarget("org.example.Editor", 42, "0x2a")
STATE = ProviderWindowState("0x2a", 42, 10, 20, 800, 600, True)


class FakeProvider:
    def __init__(
        self, frames=(PNG_A,), state=STATE, available=True, input_available=None,
    ):
        self.frames = list(frames)
        self.state = state
        self.is_available = available
        self.is_input_available = available if input_available is None else input_available
        self.injected = []

    def capture_available(self):
        return self.is_available

    def input_available(self):
        return self.is_input_available

    def inspect(self, target):
        return self.state

    def capture(self, target, maximum_source_pixels, maximum_pixels, maximum_bytes):
        image = self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]
        return ProviderScreenFrame(self.state, 800, 600, image)

    def inject(self, target, action):
        self.injected.append(action)
        return True


class ScreenObservationTests(unittest.TestCase):
    def test_capture_is_window_scoped_bounded_and_digest_verified(self):
        observation = ScreenInputBridge(FakeProvider(), clock=lambda: NOW).observe(TARGET)
        self.assertIsNone(observation.issue_code)
        self.assertEqual(hashlib.sha256(PNG_A).hexdigest(), observation.frame.image_sha256)
        self.assertIn("0x2a:800x600", observation.frame.scene_id)
        self.assertEqual(TARGET, observation.frame.target)

    def test_unavailable_mismatched_and_oversized_providers_fail_closed(self):
        unavailable = ScreenInputBridge(FakeProvider(available=False), clock=lambda: NOW)
        self.assertEqual("screen.unavailable", unavailable.observe(TARGET).issue_code)
        wrong = ProviderWindowState("0x2b", 42, 0, 0, 100, 100, True)
        mismatch = ScreenInputBridge(FakeProvider(state=wrong), clock=lambda: NOW)
        self.assertEqual("screen.capture_failed", mismatch.observe(TARGET).issue_code)
        policy = ScreenInputPolicy(maximum_encoded_bytes=8)
        oversized = ScreenInputBridge(FakeProvider(), policy, clock=lambda: NOW)
        self.assertEqual("screen.capture_failed", oversized.observe(TARGET).issue_code)

    def test_capture_authority_remains_available_without_input_backend(self):
        provider = FakeProvider(input_available=False)
        bridge = ScreenInputBridge(provider, clock=lambda: NOW)
        scene = bridge.observe(TARGET).frame.scene_id
        click = ScreenInputInstruction(
            ScreenInputKind.POINTER_CLICK, RelativeScreenPoint(1, 1)
        )
        with self.assertRaisesRegex(RuntimeError, "input is unavailable"):
            bridge.prepare_action("screen.no_input", TARGET, scene, click)


class ScreenInputActionTests(unittest.TestCase):
    def test_action_is_scene_bound_rechecked_and_emits_postframe_evidence(self):
        provider = FakeProvider()
        bridge = ScreenInputBridge(provider, clock=lambda: NOW)
        scene = bridge.observe(TARGET).frame.scene_id
        instruction = ScreenInputInstruction(
            ScreenInputKind.POINTER_CLICK, RelativeScreenPoint(500_000, 250_000)
        )
        proposal = bridge.prepare_action("screen.operation", TARGET, scene, instruction)
        evidence = bridge.perform_action(proposal)
        self.assertTrue(evidence.invoked)
        self.assertEqual(scene, evidence.before_scene_id)
        self.assertEqual(scene, evidence.after_scene_id)
        self.assertEqual(1, len(provider.injected))

    def test_stale_scene_is_rejected_after_approval_without_input(self):
        provider = FakeProvider((PNG_A, PNG_A, PNG_B))
        bridge = ScreenInputBridge(provider, clock=lambda: NOW)
        scene = bridge.observe(TARGET).frame.scene_id
        instruction = ScreenInputInstruction(
            ScreenInputKind.POINTER_CLICK, RelativeScreenPoint(1, 1)
        )
        proposal = bridge.prepare_action("screen.stale", TARGET, scene, instruction)
        with self.assertRaisesRegex(RuntimeError, "changed after approval"):
            bridge.perform_action(proposal)
        self.assertEqual([], provider.injected)

    def test_unlisted_key_and_unfocused_window_are_rejected(self):
        bridge = ScreenInputBridge(FakeProvider(), clock=lambda: NOW)
        scene = bridge.observe(TARGET).frame.scene_id
        dangerous = ScreenInputInstruction(ScreenInputKind.KEY_CHORD, keys=("Delete",))
        with self.assertRaises(PermissionError):
            bridge.prepare_action("screen.denied", TARGET, scene, dangerous)
        unfocused = ProviderWindowState("0x2a", 42, 0, 0, 100, 100, False)
        hidden = ScreenInputBridge(FakeProvider(state=unfocused), clock=lambda: NOW)
        self.assertEqual("screen.capture_failed", hidden.observe(TARGET).issue_code)

    def test_registration_is_exact_scope_always_confirmed_and_irreversible(self):
        registration = build_screen_input_registration(
            "screen.connector", "screen.instance", TARGET.application_id,
            TARGET.process_id, TARGET.window_id, NOW,
        )
        self.assertIs(ConnectorTransportKind.SCREEN_INPUT, registration.transport_kind)
        action = registration.capabilities[1].capability
        self.assertIs(ConfirmationPolicy.ALWAYS, action.confirmation)
        self.assertEqual(TARGET.scope, registration.capabilities[1].resource_scopes)


if __name__ == "__main__":
    unittest.main()
