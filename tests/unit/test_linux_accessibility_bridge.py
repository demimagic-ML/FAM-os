import unittest
from dataclasses import replace
from datetime import datetime, timezone

from fam_os.adapters.linux.accessibility import (
    AccessibilityBridgePolicy,
    LinuxAccessibilityBridge,
    build_accessibility_registration,
)
from fam_os.adapters.linux.accessibility.types import (
    ProviderAccessibleAction,
    ProviderAccessibleNode,
)
from fam_os.applications import ConfirmationPolicy, ConnectorTransportKind


class LinuxAccessibilityObservationTests(unittest.TestCase):
    def test_tree_is_bounded_allowlisted_and_protected_content_is_redacted(self):
        provider = FakeProvider.standard()
        bridge = LinuxAccessibilityBridge(
            provider,
            AccessibilityBridgePolicy(
                maximum_nodes=3,
                maximum_depth=2,
                maximum_text_characters=4,
                maximum_actions_per_node=1,
            ),
            clock=lambda: NOW,
        )

        snapshot = bridge.observe(100, include_text=True)

        self.assertEqual(3, len(snapshot.nodes))
        self.assertTrue(snapshot.truncated)
        button = snapshot.nodes[1]
        self.assertEqual(("click",), tuple(item.name for item in button.actions))
        self.assertEqual("save", button.text)
        password = snapshot.nodes[2]
        self.assertTrue(password.protected)
        self.assertIsNone(password.name)
        self.assertIsNone(password.description)
        self.assertIsNone(password.text)
        self.assertEqual((), password.actions)

    def test_text_requires_explicit_request_and_unavailable_is_explicit(self):
        provider = FakeProvider.standard()
        snapshot = LinuxAccessibilityBridge(provider, clock=lambda: NOW).observe(100)
        self.assertTrue(all(node.text is None for node in snapshot.nodes))
        provider.is_available = False
        unavailable = LinuxAccessibilityBridge(provider, clock=lambda: NOW).observe(100)
        self.assertEqual("accessibility.unavailable", unavailable.issue_code)
        self.assertEqual((), unavailable.nodes)

    def test_ambiguous_process_root_is_not_selected(self):
        provider = FakeProvider.standard()
        provider.root_handles = ("root", "duplicate")
        provider.nodes["duplicate"] = provider.nodes["root"]
        provider.children["duplicate"] = []
        snapshot = LinuxAccessibilityBridge(provider, clock=lambda: NOW).observe(100)
        self.assertEqual("accessibility.unavailable", snapshot.issue_code)


class LinuxAccessibilityActionTests(unittest.TestCase):
    def test_action_is_prepared_revalidated_and_reports_raw_invocation(self):
        provider = FakeProvider.standard()
        bridge = LinuxAccessibilityBridge(provider, clock=lambda: NOW)
        reference = bridge.observe(100).nodes[1].reference

        proposal = bridge.prepare_action("operation-1", reference, "CLICK")
        evidence = bridge.perform_action(proposal)

        self.assertEqual(("button", 0), provider.performed)
        self.assertTrue(evidence.invoked)
        self.assertEqual(reference.fingerprint, evidence.before_fingerprint)
        self.assertEqual(reference.fingerprint, evidence.after_fingerprint)

    def test_changed_identity_is_rejected_before_action(self):
        provider = FakeProvider.standard()
        bridge = LinuxAccessibilityBridge(provider, clock=lambda: NOW)
        reference = bridge.observe(100).nodes[1].reference
        provider.nodes["button"] = replace(provider.nodes["button"], name="Changed")
        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            bridge.prepare_action("operation-2", reference, "click")
        self.assertIsNone(provider.performed)

    def test_changed_action_after_approval_is_rejected(self):
        provider = FakeProvider.standard()
        bridge = LinuxAccessibilityBridge(provider, clock=lambda: NOW)
        reference = bridge.observe(100).nodes[1].reference
        proposal = bridge.prepare_action("operation-3", reference, "click")
        provider.nodes["button"] = replace(
            provider.nodes["button"],
            actions=(ProviderAccessibleAction(0, "press"),),
        )
        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            bridge.perform_action(proposal)
        self.assertIsNone(provider.performed)

    def test_protected_and_unlisted_actions_are_rejected(self):
        provider = FakeProvider.standard()
        bridge = LinuxAccessibilityBridge(provider, clock=lambda: NOW)
        snapshot = bridge.observe(100)
        with self.assertRaises(PermissionError):
            bridge.prepare_action("operation-4", snapshot.nodes[2].reference, "click")
        with self.assertRaises(PermissionError):
            bridge.prepare_action("operation-5", snapshot.nodes[1].reference, "destroy")

    def test_action_omitted_by_bound_cannot_be_invoked(self):
        provider = FakeProvider.standard()
        provider.nodes["button"] = replace(
            provider.nodes["button"],
            actions=(
                ProviderAccessibleAction(0, "press"),
                ProviderAccessibleAction(1, "click"),
            ),
        )
        bridge = LinuxAccessibilityBridge(
            provider, AccessibilityBridgePolicy(maximum_actions_per_node=1)
        )
        button = bridge.observe(100).nodes[1]
        self.assertEqual(("press",), tuple(item.name for item in button.actions))
        with self.assertRaisesRegex(ValueError, "no longer available"):
            bridge.prepare_action("operation-6", button.reference, "click")


class LinuxAccessibilityCatalogTests(unittest.TestCase):
    def test_registration_is_process_scoped_and_actions_always_confirmed(self):
        registration = build_accessibility_registration(
            "atspi-connector", "atspi-instance", 100, NOW
        )
        self.assertEqual(ConnectorTransportKind.ACCESSIBILITY, registration.transport_kind)
        self.assertTrue(all(entry.resource_scopes == ("process:100",) for entry in registration.capabilities))
        action = registration.capabilities[1].capability
        self.assertEqual(ConfirmationPolicy.ALWAYS, action.confirmation)
        self.assertEqual(("accessibility.action.poststate",), action.postcondition_ids)


class FakeProvider:
    def __init__(self, nodes, children):
        self.nodes = nodes
        self.children = children
        self.root_handles = ("root",)
        self.is_available = True
        self.performed = None

    @classmethod
    def standard(cls):
        click = ProviderAccessibleAction(0, "click", "Click it", "Enter")
        destroy = ProviderAccessibleAction(1, "destroy")
        nodes = {
            "root": _node("application", "Editor", child_count=3),
            "button": _node(
                "push button", "Save", actions=(click, destroy), text="save",
                text_truncated=True,
            ),
            "password": _node(
                "password text", "secret", actions=(click,), text="hunter2",
                protected=True,
            ),
            "panel": _node("panel", "Tools", child_count=1),
            "deep": _node("label", "Deep"),
        }
        children = {
            "root": ["button", "password", "panel"],
            "button": [], "password": [], "panel": ["deep"], "deep": [],
        }
        return cls(nodes, children)

    def available(self):
        return self.is_available

    def roots(self):
        return self.root_handles

    def read(self, handle, maximum_text_characters, include_text=False):
        node = self.nodes[handle]
        if not include_text:
            return replace(node, text=None, text_truncated=False)
        if node.text is None or len(node.text) <= maximum_text_characters:
            return node
        return replace(
            node, text=node.text[:maximum_text_characters], text_truncated=True
        )

    def child(self, handle, index):
        values = self.children.get(handle, [])
        return values[index] if 0 <= index < len(values) else None

    def perform_action(self, handle, action_index):
        self.performed = (handle, action_index)
        return True


def _node(
    role, name, *, actions=(), text=None, protected=False,
    child_count=0, text_truncated=False,
):
    return ProviderAccessibleNode(
        100, role, name, "description", ("enabled",), actions, text,
        protected, child_count, text_truncated,
    )


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
