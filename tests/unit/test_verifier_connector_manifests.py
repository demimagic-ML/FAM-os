import unittest

from fam_os.applications import (
    CONNECTOR_MANIFEST_CONTRACT_VERSION,
    ApplicationAuthority,
    CapabilityDescriptor,
    CapabilityKind,
    ConnectorManifest,
    ConfirmationPolicy,
    Reversibility,
)
from fam_os.registry import ArtifactDigest, PackageMetadata, PackageTrustLevel
from fam_os.verification import (
    VERIFIER_MANIFEST_CONTRACT_VERSION,
    DeterminismClass,
    VerifierManifest,
)


def _package(package_id: str) -> PackageMetadata:
    return PackageMetadata(
        package_id=package_id,
        package_version="1.0.0",
        publisher_id="fam-project",
        license_id="Apache-2.0",
        trust_level=PackageTrustLevel.BUILT_IN,
        artifact_digest=ArtifactDigest("sha256", "b" * 64),
    )


def _verifier(**overrides: object) -> VerifierManifest:
    values = {
        "package": _package("fam.verifier.python-tests"),
        "verifier_id": "verifier.python.tests",
        "display_name": "Python tests",
        "runner_contract_id": "fam.verification.sandbox/v1",
        "acceptance_ids": ("acceptance.python.unit-tests",),
        "candidate_schema_ids": ("schema.code.python",),
        "evidence_schema_id": "schema.verification.process-evidence",
        "determinism": DeterminismClass.DETERMINISTIC,
        "required_isolation_capabilities": (
            "isolation.process-limits",
            "isolation.filesystem-denied-by-default",
            "isolation.network-denied",
        ),
        "timeout_seconds": 10.0,
    }
    values.update(overrides)
    return VerifierManifest(**values)


def _observation() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id="editor.observe.active_document",
        display_name="Observe active document",
        description="Read editor document identity and version.",
        kind=CapabilityKind.OBSERVATION,
        required_authority=ApplicationAuthority.OBSERVE,
        input_schema_id="schema.editor.observe-request",
        output_schema_id="schema.editor.document-state",
    )


def _action() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id="editor.modify.workspace_edit",
        display_name="Apply workspace edit",
        description="Prepare and apply a reversible editor workspace edit.",
        kind=CapabilityKind.ACTION,
        required_authority=ApplicationAuthority.MODIFY,
        input_schema_id="schema.editor.workspace-edit",
        output_schema_id="schema.editor.action-result",
        reversibility=Reversibility.REVERSIBLE,
        confirmation=ConfirmationPolicy.WHEN_REQUIRED,
        postcondition_ids=("postcondition.document-hash",),
    )


def _connector(**overrides: object) -> ConnectorManifest:
    values = {
        "package": _package("fam.connector.code-editor"),
        "connector_id": "connector.code-editor.reference",
        "display_name": "Reference code editor connector",
        "application_ids": ("application.code-editor",),
        "capabilities": (_observation(), _action()),
        "transport_protocol_ids": ("fam.local-intent/v1", "semantic-tools/v1"),
        "requested_authorities": (
            ApplicationAuthority.OBSERVE,
            ApplicationAuthority.MODIFY,
        ),
        "sandbox_profile_id": "sandbox.connector.default",
        "supports_dynamic_capabilities": True,
    }
    values.update(overrides)
    return ConnectorManifest(**values)


class VerifierManifestTests(unittest.TestCase):
    def test_declares_acceptance_evidence_isolation_and_determinism(self) -> None:
        manifest = _verifier()
        self.assertEqual(manifest.contract_version, VERIFIER_MANIFEST_CONTRACT_VERSION)
        self.assertIn(
            "isolation.filesystem-denied-by-default",
            manifest.required_isolation_capabilities,
        )
        self.assertFalse(manifest.network_access)

    def test_deterministic_verifier_cannot_require_network(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot require network"):
            _verifier(network_access=True)

    def test_rejects_duplicate_acceptance_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "acceptance_ids values must be unique"):
            _verifier(acceptance_ids=("acceptance.python", "acceptance.python"))


class ConnectorManifestTests(unittest.TestCase):
    def test_static_manifest_is_protocol_neutral_and_authority_explicit(self) -> None:
        manifest = _connector()
        self.assertEqual(manifest.contract_version, CONNECTOR_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(len(manifest.transport_protocol_ids), 2)
        self.assertIn(ApplicationAuthority.MODIFY, manifest.requested_authorities)

    def test_requested_authorities_cover_capabilities(self) -> None:
        with self.assertRaisesRegex(ValueError, "cover declared capabilities"):
            _connector(requested_authorities=(ApplicationAuthority.OBSERVE,))

    def test_rejects_duplicate_transport_protocol_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be unique"):
            _connector(transport_protocol_ids=("fam.local/v1", "fam.local/v1"))


if __name__ == "__main__":
    unittest.main()
