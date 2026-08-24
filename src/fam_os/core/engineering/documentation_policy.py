"""Deterministic policy selecting governed generated-content requirements."""

from fam_os.core.engineering.documentation import DocumentationArtifactKind


class DocumentationRequirementPolicy:
    policy_id = "fam.documentation.requirements.v1"

    _TERMS = {
        DocumentationArtifactKind.DIAGRAM: (
            "architecture", "diagram", "topology", "design migration",
        ),
        DocumentationArtifactKind.API_REFERENCE: (
            " api ", "endpoint", "route", "openapi", "interface reference",
        ),
        DocumentationArtifactKind.RUNBOOK: (
            "runbook", "deploy", "deployment", "kubernetes", "container",
            "systemd", "operations",
        ),
        DocumentationArtifactKind.CHANGELOG: (
            "changelog", "release note", "release documentation",
        ),
        DocumentationArtifactKind.GENERATED_CODE: (
            "generated code", "codegen", "code generation", "scaffold",
        ),
    }

    def required_kinds(
        self, intent: str,
    ) -> tuple[DocumentationArtifactKind, ...]:
        normalized = f" {intent.casefold()} "
        return tuple(
            kind for kind in DocumentationArtifactKind
            if any(term in normalized for term in self._TERMS[kind])
        )


DOCUMENTATION_OUTPUT_PATHS = {
    DocumentationArtifactKind.DIAGRAM: "docs/generated/fam-architecture.mmd",
    DocumentationArtifactKind.API_REFERENCE: "docs/generated/fam-api-reference.md",
    DocumentationArtifactKind.RUNBOOK: "docs/generated/fam-runbook.md",
    DocumentationArtifactKind.CHANGELOG: "docs/generated/fam-changelog.md",
    DocumentationArtifactKind.GENERATED_CODE: "generated/fam_source_manifest.py",
}

DOCUMENTATION_OWNERSHIP_PATH = "docs/generated/FAM_OWNERSHIP.md"
DOCUMENTATION_REGENERATION_PATH = "docs/generated/FAM_REGENERATE.md"
DOCUMENTATION_REQUIREMENTS_PATH = "docs/generated/FAM_REQUIREMENTS.md"
