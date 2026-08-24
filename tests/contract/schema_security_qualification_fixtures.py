"""Representative incomplete engineering security qualification documents."""

from datetime import timedelta

from fam_os.core.engineering import (
    EngineeringPressureSoakReport,
    EngineeringQualificationStatus,
    EngineeringSecurityReview,
    InstalledEngineeringQualification,
)
from tests.contract.schema_engineering_fixtures import NOW


def security_qualification_schema_values() -> tuple[object, ...]:
    review = EngineeringSecurityReview(
        "review-1", "release-1", "independent-reviewer-1", True,
        (
            "command_execution", "dependency_network_authority",
            "creative_file_parsers", "git_credentials",
            "remote_publication", "self_modification",
        ),
        ("finding-1",), (), "a" * 64, "b" * 64, NOW,
    )
    soak = EngineeringPressureSoakReport(
        "soak-1", "release-1", NOW, NOW + timedelta(seconds=60), 60,
        1, 1, 1, 0, 1, 1, 1, 0, 1, "c" * 64,
        EngineeringQualificationStatus.INCOMPLETE,
    )
    qualification = InstalledEngineeringQualification(
        "qualification-1", "release-1", ("compat-cpu-16gb",),
        ("offline-python",), ("language-python",), ("scenario-candidate",),
        (("symlink_race", "security-test-1"),), None, None, None,
        EngineeringQualificationStatus.INCOMPLETE, NOW,
    )
    return review, soak, qualification
