import sys
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.codex_subscription import (
    CodexSubscriptionRuntime, CodexSubscriptionSettings,
)
from fam_os.product.composition.engineering_inference import (
    compose_engineering_inference,
)


class EngineeringInferenceCompositionTests(unittest.TestCase):
    def test_local_runtime_remains_default(self):
        local = object()
        result = compose_engineering_inference(local, "local:1", None)
        self.assertIs(local, result.runtime)
        self.assertEqual("local:1", result.model_ref)

    def test_codex_subscription_is_engineering_only_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = CodexSubscriptionSettings(
                Path(sys.executable), Path(temporary) / "work", Path.home(),
            )
            provided = object()
            result = compose_engineering_inference(
                object(), "local:1", settings, provided,
            )
            self.assertIs(provided, result.runtime)
            self.assertEqual("gpt-5.6-sol", result.model_ref)

            composed = compose_engineering_inference(
                object(), "local:1", settings,
            )
            self.assertIsInstance(composed.runtime, CodexSubscriptionRuntime)


if __name__ == "__main__":
    unittest.main()
