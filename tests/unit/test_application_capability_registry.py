import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fam_os.applications import (
    ApplicationAuthority, ApplicationCapabilityRegistry, ApplicationIdentity,
    ApplicationInstance, CapabilityDescriptor, CapabilityKind,
    CapabilityRegistryEntry, ConnectorRegistration, ConnectorTransportKind,
    RegistryEventKind,
)


NOW = datetime(2026, 7, 16, 23, 30, tzinfo=timezone.utc)


class ApplicationCapabilityRegistryTests(unittest.TestCase):
    def test_register_lookup_snapshot_and_event_are_deterministic(self):
        registry = self.registry()
        registry.register(registration("connector-b", "instance-b", "entry-b"))
        registry.register(registration("connector-a", "instance-a", "entry-a"))

        snapshot = registry.snapshot()
        self.assertEqual(2, snapshot.revision)
        self.assertEqual(("connector-a", "connector-b"), tuple(
            item.connector_id for item in snapshot.registrations
        ))
        self.assertEqual("entry-a", registry.lookup("instance-a", "editor.observe").entry_id)
        self.assertEqual((1, 2), tuple(event.revision for event in registry.events()))
        self.assertTrue(all(event.kind is RegistryEventKind.REGISTERED for event in registry.events()))

    def test_same_connector_replacement_atomically_removes_old_indexes(self):
        registry = self.registry()
        registry.register(registration("connector-1", "instance-1", "old-entry", "old.observe"))
        registry.register(registration("connector-1", "instance-1", "new-entry", "new.observe"))

        self.assertIsNone(registry.lookup("instance-1", "old.observe"))
        self.assertEqual("new-entry", registry.lookup("instance-1", "new.observe").entry_id)
        self.assertEqual(RegistryEventKind.REPLACED, registry.events()[-1].kind)
        self.assertEqual(2, registry.snapshot().revision)

    def test_foreign_collision_rejects_without_partial_mutation_or_event(self):
        registry = self.registry()
        registry.register(registration("connector-1", "instance-1", "shared-entry"))
        before = registry.snapshot()
        with self.assertRaisesRegex(ValueError, "entry ID"):
            registry.register(registration("connector-2", "instance-2", "shared-entry"))
        self.assertEqual(before, registry.snapshot())
        self.assertEqual(1, len(registry.events()))

    def test_instance_ownership_collision_is_rejected(self):
        registry = self.registry()
        registry.register(registration("connector-1", "instance-1", "entry-1"))
        with self.assertRaisesRegex(ValueError, "instance"):
            registry.register(registration("connector-2", "instance-1", "entry-2"))

    def test_availability_change_is_atomic_idempotent_and_auditable(self):
        registry = self.registry()
        registry.register(registration("connector-1", "instance-1", "entry-1"))
        registry.set_availability("connector-1", "instance-1", "editor.observe", False)
        self.assertFalse(registry.lookup("instance-1", "editor.observe").available)
        event = registry.events()[-1]
        self.assertEqual(RegistryEventKind.AVAILABILITY_CHANGED, event.kind)
        self.assertFalse(event.available)
        revision = registry.snapshot().revision
        registry.set_availability("connector-1", "instance-1", "editor.observe", False)
        self.assertEqual(revision, registry.snapshot().revision)

    def test_unregister_removes_indexes_and_unknown_remove_is_idempotent(self):
        registry = self.registry()
        registry.register(registration("connector-1", "instance-1", "entry-1"))
        registry.unregister("connector-1")
        self.assertEqual((), registry.entries())
        self.assertEqual(RegistryEventKind.REMOVED, registry.events()[-1].kind)
        revision = registry.snapshot().revision
        registry.unregister("connector-1")
        self.assertEqual(revision, registry.snapshot().revision)

    def test_concurrent_distinct_registrations_preserve_every_index(self):
        registry = ApplicationCapabilityRegistry()
        values = tuple(
            registration(f"connector-{index}", f"instance-{index}", f"entry-{index}")
            for index in range(20)
        )
        with ThreadPoolExecutor(max_workers=8) as executor:
            tuple(executor.map(registry.register, values))
        self.assertEqual(20, registry.snapshot().revision)
        self.assertEqual(20, len(registry.entries()))
        self.assertEqual(20, len(registry.events()))

    def test_event_construction_failure_leaves_registry_unchanged(self):
        registry = ApplicationCapabilityRegistry(
            clock=lambda: NOW,
            event_id_factory=lambda: (_ for _ in ()).throw(RuntimeError("no event")),
        )
        before = registry.snapshot()
        with self.assertRaisesRegex(RuntimeError, "no event"):
            registry.register(registration("connector-1", "instance-1", "entry-1"))
        self.assertEqual(before, registry.snapshot())
        self.assertEqual((), registry.events())

    def registry(self):
        ids = iter(range(20))
        return ApplicationCapabilityRegistry(
            clock=lambda: NOW, event_id_factory=lambda: f"event-{next(ids)}"
        )


def registration(connector_id, instance_id, entry_id, capability_id="editor.observe"):
    application = ApplicationIdentity("org.example.editor", "Example Editor")
    instance = ApplicationInstance(instance_id, application, connector_id, 10)
    capability = CapabilityDescriptor(
        capability_id, "Observe editor", "Observe editor state",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "editor.observe.input", "editor.observe.output",
    )
    entry = CapabilityRegistryEntry(
        entry_id, connector_id, instance_id, application.application_id, capability
    )
    return ConnectorRegistration(
        connector_id, ConnectorTransportKind.NATIVE_LOCAL, "test.connector", "1",
        instance, (entry,), NOW,
    )


if __name__ == "__main__":
    unittest.main()
