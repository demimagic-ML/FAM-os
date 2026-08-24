import unittest
from types import SimpleNamespace

from fam_os.core.production.application_generation import application_grounded_context


class ApplicationGenerationTests(unittest.TestCase):
    def test_selected_workspace_is_explicit_model_grounding(self):
        application = SimpleNamespace(
            resource_uri="file:///home/owner/Soccer_Oracle/",
            application_instance_id="owner-filesystem",
            observations=(),
        )
        snapshot = SimpleNamespace(plan=SimpleNamespace(steps=()))

        context = application_grounded_context(application, snapshot)

        self.assertIn("Authorized selection:", context)
        self.assertIn(
            "Selected workspace or resource: file:///home/owner/Soccer_Oracle/",
            context,
        )
        self.assertIn("Selected application instance: owner-filesystem", context)


if __name__ == "__main__":
    unittest.main()
