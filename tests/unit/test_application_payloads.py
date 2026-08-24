import unittest

from fam_os.applications.payloads import freeze_payload, thaw_payload


class ApplicationPayloadTests(unittest.TestCase):
    def test_thaw_preserves_nested_json_shape(self):
        frozen = freeze_payload({
            "document_uri": "file:///workspace/main.py",
            "edits": [{
                "range": {"start": {"line": 0, "character": 0}},
                "new_text": "after",
            }],
        })
        thawed = thaw_payload(frozen)
        self.assertIsInstance(thawed, dict)
        self.assertIsInstance(thawed["edits"], list)
        self.assertEqual(0, thawed["edits"][0]["range"]["start"]["line"])


if __name__ == "__main__":
    unittest.main()
