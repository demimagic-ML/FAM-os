import unittest
from types import SimpleNamespace

from fam_os.core.contracts import PlanStepKind
from fam_os.core.production.gateway import _progress_message


class GatewayProgressTests(unittest.TestCase):
    def test_prepare_action_message_is_stable_while_model_selection_changes(self):
        snapshot = _snapshot(PlanStepKind.PREPARE_ACTION)

        weak = _record("qwen2.5-coder:7b")
        strong = _record("laguna-xs.2:q4_K_M")

        self.assertEqual(_progress_message(weak, snapshot), _progress_message(strong, snapshot))
        self.assertEqual(
            "Resolving a bounded action proposal from authorized evidence",
            _progress_message(strong, snapshot),
        )

    def test_inference_progress_still_names_the_selected_model(self):
        self.assertEqual(
            "Running gemma4:26b",
            _progress_message(_record("gemma4:26b"), _snapshot(PlanStepKind.INFERENCE)),
        )


def _record(model_ref):
    return SimpleNamespace(selection=SimpleNamespace(model_ref=model_ref))


def _snapshot(kind):
    step = SimpleNamespace(step_id="current", kind=kind)
    return SimpleNamespace(
        terminal=False,
        current_step_id="current",
        plan=SimpleNamespace(steps=(step,)),
    )


if __name__ == "__main__":
    unittest.main()
