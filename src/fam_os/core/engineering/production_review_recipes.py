"""Release-owned deterministic independent reviewer specification."""

from dataclasses import dataclass

from fam_os.core.engineering.review import EngineeringReviewDiscipline


@dataclass(frozen=True, slots=True)
class EngineeringReviewerRecipeSpecification:
    recipe_id: str
    reviewer_id: str
    adapter_id: str
    disciplines: tuple[EngineeringReviewDiscipline, ...]


def initial_engineering_reviewer_recipe_specification(
) -> EngineeringReviewerRecipeSpecification:
    return EngineeringReviewerRecipeSpecification(
        "fam.engineering.independent-review",
        "fam-release-independent-reviewer-v1",
        "fam.review.deterministic.v1",
        tuple(EngineeringReviewDiscipline),
    )
