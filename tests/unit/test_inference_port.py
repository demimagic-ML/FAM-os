import unittest

from fam_os.core.ports.inference import (
    InferenceMessage,
    InferenceRequest,
    LoadedModel,
    MessageRole,
)


class InferenceRequestTests(unittest.TestCase):
    def test_has_no_ollama_specific_fields(self) -> None:
        request = InferenceRequest(
            model_ref="granite3.3:2b",
            messages=(InferenceMessage(MessageRole.USER, "route this"),),
            context_tokens=8192,
            max_output_tokens=100,
            json_output=True,
        )
        self.assertEqual(request.model_ref, "granite3.3:2b")
        self.assertFalse(hasattr(request, "ollama_url"))

    def test_requires_messages(self) -> None:
        with self.assertRaisesRegex(ValueError, "message"):
            InferenceRequest("model", (), 2048, 100)

    def test_rejects_negative_temperature(self) -> None:
        with self.assertRaisesRegex(ValueError, "temperature"):
            InferenceRequest(
                "model",
                (InferenceMessage(MessageRole.USER, "hello"),),
                2048,
                100,
                temperature=-0.1,
            )

    def test_rejects_invalid_accelerator_placement(self) -> None:
        message = (InferenceMessage(MessageRole.USER, "hello"),)
        with self.assertRaisesRegex(ValueError, "layer_count"):
            InferenceRequest("model", message, 2048, 100, accelerator_layer_count=-1)
        with self.assertRaisesRegex(ValueError, "main accelerator"):
            InferenceRequest("model", message, 2048, 100, main_accelerator_index=0)

    def test_accepts_explicit_provider_neutral_layer_placement(self) -> None:
        request = InferenceRequest(
            "model", (InferenceMessage(MessageRole.USER, "hello"),), 2048, 100,
            accelerator_layer_count=12, main_accelerator_index=0,
        )
        self.assertEqual(request.accelerator_layer_count, 12)

    def test_loaded_model_resource_values_cannot_be_negative(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            LoadedModel("model", resident_bytes=-1)


if __name__ == "__main__":
    unittest.main()
