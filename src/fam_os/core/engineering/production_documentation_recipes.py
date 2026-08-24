"""Release-owned deterministic documentation generator specifications."""

from dataclasses import dataclass

from fam_os.core.engineering.documentation import DocumentationArtifactKind


@dataclass(frozen=True, slots=True)
class DocumentationRecipeSpecification:
    recipe_id: str
    kind: DocumentationArtifactKind
    generator_id: str
    output_media_type: str
    maximum_source_files: int = 64
    maximum_source_bytes: int = 2_097_152
    maximum_output_bytes: int = 262_144


def initial_documentation_recipe_specifications(
) -> tuple[DocumentationRecipeSpecification, ...]:
    return tuple(
        DocumentationRecipeSpecification(
            f"fam.documentation.{kind.value}", kind,
            "fam.documentation.deterministic.v1",
            "text/vnd.mermaid" if kind is DocumentationArtifactKind.DIAGRAM
            else "text/x-python" if kind is DocumentationArtifactKind.GENERATED_CODE
            else "text/markdown",
        )
        for kind in DocumentationArtifactKind
    )
