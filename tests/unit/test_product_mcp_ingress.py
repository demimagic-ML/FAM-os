import json
import os
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from fam_os.product.composition.mcp_ingress import ProductMcpIngress


class ProductMcpIngressConfigurationTests(unittest.TestCase):
    def test_disabled_private_configuration_opens_no_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "mcp-ingress.json"
            document = _document(False, [])
            path.write_text(json.dumps(document), encoding="utf-8")
            os.chmod(path, 0o600)
            ingress = ProductMcpIngress.from_file(
                path, root / "mcp.sock", os.geteuid(), None, None,
            )
            self.assertFalse(ingress.enabled)
            ingress.start()
            ingress.close()
            self.assertFalse((root / "mcp.sock").exists())

    def test_configuration_is_owner_private_and_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "mcp-ingress.json"
            path.write_text(json.dumps(_document(False, [])), encoding="utf-8")
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                ProductMcpIngress.from_file(
                    path, root / "mcp.sock", os.geteuid(), None, None,
                )
            os.chmod(path, 0o600)
            malformed = _document(False, [])
            malformed["unexpected"] = True
            path.write_text(json.dumps(malformed), encoding="utf-8")
            with self.assertRaises(ValueError):
                ProductMcpIngress.from_file(
                    path, root / "mcp.sock", os.geteuid(), None, None,
                )

    def test_versioned_schema_accepts_allowlist_and_rejects_unknown_capability(self):
        schema = json.loads(Path(
            "schemas/v1alpha1/fam.product.mcp-ingress-config.schema.json"
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        valid = _document(True, [{
            "client_id": "editor-client", "principal_id": "local-editor",
            "capabilities": ["fam.ask"], "session_ttl_seconds": 3600,
        }])
        validator.validate(valid)
        invalid = json.loads(json.dumps(valid))
        invalid["clients"][0]["capabilities"] = ["fam.admin"]
        with self.assertRaises(ValidationError):
            validator.validate(invalid)


def _document(enabled, clients):
    return {
        "contract_version": "fam.product.mcp-ingress/v1alpha1",
        "enabled": enabled,
        "clients": clients,
    }


if __name__ == "__main__":
    unittest.main()
