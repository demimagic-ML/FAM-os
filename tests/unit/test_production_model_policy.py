import unittest

from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.intent import DeterministicIntentClassifier
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import ResourceAwareModelSelector
from fam_os.core.production.model_selection import HostCapacity


class ProductionModelPolicyTests(unittest.TestCase):
    def test_intent_policy_does_not_hide_mutating_capability(self) -> None:
        classifier = DeterministicIntentClassifier()
        self.assertEqual(
            ModelIntent.APPLICATION_MUTATION,
            classifier.classify("please do it", ("vscode.workspace.edit",)),
        )
        self.assertEqual(
            ModelIntent.APPLICATION_MUTATION,
            classifier.classify("implement it", ("os.workspace.patch",)),
        )
        self.assertEqual(ModelIntent.CODE, classifier.classify("fix this Python test"))

    def test_explicit_local_workspace_question_routes_to_grounded_retrieval(self) -> None:
        classifier = DeterministicIntentClassifier()
        self.assertEqual(
            ModelIntent.GROUNDED_QUESTION,
            classifier.classify(
                "What exact PHASE23_WORKSPACE_FACT statement is in this workspace?"
            ),
        )
        self.assertEqual(
            ModelIntent.CONVERSATION,
            classifier.classify("Are collaborative workspaces useful?"),
        )

    def test_selector_uses_economical_then_strong_fitting_model(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("small:1", "economical", 2),
            _entry("large:1", "escalation", 18),
        ))
        selector = ResourceAwareModelSelector(catalog)
        capacity = HostCapacity(48 * 1024**3, 16 * 1024**3)
        self.assertEqual(
            "small:1", selector.select("request", ModelIntent.CODE, capacity).model_ref,
        )
        self.assertEqual(
            "large:1",
            selector.select("request", ModelIntent.CODE, capacity, escalation=True).model_ref,
        )

    def test_selector_prefers_an_already_resident_capable_model(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("small:1", "economical", 2),
            _entry("resident:1", "economical", 3),
        ))
        selected = ResourceAwareModelSelector(catalog).select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
            resident_model_refs=("resident:1",),
        )
        self.assertEqual("resident:1", selected.model_ref)
        self.assertIn("residency.already_loaded", selected.reason_codes)

    def test_resident_strong_model_cannot_preempt_economical_primary(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("cold-economical:1", "economical", 2),
            _entry("resident-strong:1", "escalation", 4),
        ))

        selected = ResourceAwareModelSelector(catalog).select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
            resident_model_refs=("resident-strong:1",),
        )

        self.assertEqual("cold-economical:1", selected.model_ref)
        self.assertIn("policy.economical_first", selected.reason_codes)
        self.assertIn("residency.cold_load", selected.reason_codes)

    def test_escalation_uses_strong_tier_even_when_primary_remains_resident(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("resident-primary:1", "economical", 2),
            _entry("cold-strong:1", "escalation", 4),
        ))

        selected = ResourceAwareModelSelector(catalog).select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
            escalation=True, resident_model_refs=("resident-primary:1",),
        )

        self.assertEqual("cold-strong:1", selected.model_ref)
        self.assertIn("policy.strong_escalation", selected.reason_codes)

    def test_verified_frequency_breaks_ties_only_inside_policy_tier(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("cold-small:1", "economical", 2),
            _entry("verified-repeat:1", "economical", 3),
            _entry("strong:1", "escalation", 4),
        ))
        selector = ResourceAwareModelSelector(catalog, _Adaptation())

        primary = selector.select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
        )
        escalated = selector.select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
            escalation=True,
        )

        self.assertEqual("verified-repeat:1", primary.model_ref)
        self.assertIn("adaptation.verified_frequency_preference", primary.reason_codes)
        self.assertEqual("strong:1", escalated.model_ref)

    def test_operating_tier_cap_overrides_resident_and_escalation_preferences(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("small:1", "economical", 2),
            _entry("resident-strong:1", "escalation", 4),
        ))
        capacity = HostCapacity(
            16 * 1024**3, maximum_expert_tier="economical",
            reason_codes=("battery.conserve",),
        )

        selected = ResourceAwareModelSelector(catalog).select(
            "request", ModelIntent.CODE, capacity,
            escalation=True, resident_model_refs=("resident-strong:1",),
        )

        self.assertEqual("small:1", selected.model_ref)
        self.assertIn("battery.conserve", selected.reason_codes)

    def test_micro_cap_fails_closed_when_no_micro_capable_model_exists(self) -> None:
        catalog = RuntimeModelCatalog((_entry("small:1", "economical", 2),))
        with self.assertRaisesRegex(LookupError, "live resource budget"):
            ResourceAwareModelSelector(catalog).select(
                "request", ModelIntent.CODE,
                HostCapacity(16 * 1024**3, maximum_expert_tier="micro"),
            )

    def test_verified_selection_requires_declared_model_compatibility(self) -> None:
        catalog = RuntimeModelCatalog((
            _entry("incompatible:1", "economical", 2),
            _entry(
                "compatible:1", "specialist", 3,
                ("python.deterministic-tests.v1",),
            ),
        ))

        selected = ResourceAwareModelSelector(catalog).select(
            "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
            required_verifier_id="python.deterministic-tests.v1",
        )

        self.assertEqual("compatible:1", selected.model_ref)
        self.assertIn("verification.declared_compatibility", selected.reason_codes)

    def test_verified_selection_fails_closed_without_compatible_model(self) -> None:
        catalog = RuntimeModelCatalog((_entry("incompatible:1", "economical", 2),))

        with self.assertRaisesRegex(LookupError, "required verifier compatibility"):
            ResourceAwareModelSelector(catalog).select(
                "request", ModelIntent.CODE, HostCapacity(16 * 1024**3),
                required_verifier_id="python.deterministic-tests.v1",
            )


class _Adaptation:
    def preferred_model_refs(self, _intent):
        return ("verified-repeat:1",)


def _entry(model, tier, gib, verifier_ids=()):
    return RuntimeModelEntry(
        model, tier, (ModelIntent.CODE,), gib * 1024**3, 8192, "0" * 64,
        verifier_ids,
    )


if __name__ == "__main__":
    unittest.main()
