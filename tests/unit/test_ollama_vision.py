import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.ollama import OllamaSettings
from fam_os.adapters.ollama.vision import OllamaVisionAnalyzer
from fam_os.core.ports.media import ImageAnalysisRequest


class Transport:
    def __init__(self):
        self.payload = None

    def request(self, method, url, payload, timeout):
        self.payload = payload
        return {"message": {"content": "visible text"}, "eval_count": 1}


class OllamaVisionTests(unittest.TestCase):
    def test_image_is_bound_to_multimodal_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            path.write_bytes(b"image-bytes")
            transport = Transport()
            result = OllamaVisionAnalyzer(
                OllamaSettings("http://localhost:11434", 15), "vision:model", transport,
            ).analyze(ImageAnalysisRequest(path, "read", "ocr"))
        self.assertEqual("visible text", result.text)
        self.assertTrue(transport.payload["messages"][0]["images"][0])


if __name__ == "__main__":
    unittest.main()
