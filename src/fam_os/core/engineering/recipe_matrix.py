"""Decision-complete initial polyglot recipe and verifier coverage policy."""

from dataclasses import dataclass

from fam_os.core.engineering.execution import (
    EngineeringEcosystem, LanguageToolQualification, SignedToolRecipe,
    ToolQualificationStatus, ToolRecipePurpose,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


REQUIRED_PURPOSES: dict[EngineeringEcosystem, frozenset[ToolRecipePurpose]] = {
    EngineeringEcosystem.PYTHON: frozenset({ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.TYPE_CHECK, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.JAVASCRIPT: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.TYPESCRIPT: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.TYPE_CHECK, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.RUST: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.GO: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.JAVA: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.KOTLIN: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.C: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.CPP: frozenset({ToolRecipePurpose.BUILD, ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.COVERAGE, ToolRecipePurpose.PACKAGE, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.SHELL: frozenset({ToolRecipePurpose.TEST, ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.HTML: frozenset({ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
    EngineeringEcosystem.CSS: frozenset({ToolRecipePurpose.LINT, ToolRecipePurpose.FORMAT_CHECK, ToolRecipePurpose.STATIC_ANALYSIS, ToolRecipePurpose.LANGUAGE_DIAGNOSTICS}),
}


@dataclass(frozen=True, slots=True)
class PolyglotRecipeMatrix:
    matrix_id: str
    recipes: tuple[SignedToolRecipe, ...]
    qualifications: tuple[LanguageToolQualification, ...]
    project_acceptance_recipe_ids: tuple[str, ...]
    package_integrity_recipe_ids: tuple[str, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.matrix_id.strip():
            raise ValueError("polyglot recipe matrix requires an identity")
        coordinates = tuple((item.recipe_id, item.recipe_version) for item in self.recipes)
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("polyglot recipe coordinates must be unique")
        by_ecosystem = {
            ecosystem: {item.purpose for item in self.recipes if item.ecosystem is ecosystem}
            for ecosystem in EngineeringEcosystem
        }
        missing = {
            ecosystem.value: sorted(value.value for value in purposes - by_ecosystem[ecosystem])
            for ecosystem, purposes in REQUIRED_PURPOSES.items()
            if not purposes.issubset(by_ecosystem[ecosystem])
        }
        if missing:
            raise ValueError(f"polyglot recipe matrix is incomplete: {missing}")
        qualification_ecosystems = tuple(item.ecosystem for item in self.qualifications)
        if set(qualification_ecosystems) != set(EngineeringEcosystem) or len(qualification_ecosystems) != len(set(qualification_ecosystems)):
            raise ValueError("polyglot matrix requires one qualification per ecosystem")
        if any(item.status is not ToolQualificationStatus.PASSED for item in self.qualifications):
            raise ValueError("polyglot matrix cannot pass with unavailable or failed toolchains")
        if not self.project_acceptance_recipe_ids or not self.package_integrity_recipe_ids:
            raise ValueError("polyglot matrix requires acceptance and package integrity recipes")
        known = {item.recipe_id for item in self.recipes}
        if not set(self.project_acceptance_recipe_ids + self.package_integrity_recipe_ids).issubset(known):
            raise ValueError("matrix references an unknown recipe")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("polyglot matrix contract version is unsupported")
