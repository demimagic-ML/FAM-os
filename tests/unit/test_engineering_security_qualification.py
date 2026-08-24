import unittest
from dataclasses import replace

from fam_os.core.engineering import EngineeringQualificationStatus
from tests.contract.schema_security_qualification_fixtures import security_qualification_schema_values
from fam_os.core.engineering.security_coverage import validate_adversarial_coverage


class EngineeringSecurityQualificationTests(unittest.TestCase):
    def test_adversarial_coverage_ledger_names_every_required_category(self):
        validate_adversarial_coverage()

    def test_incomplete_evidence_cannot_be_relabelled_operationally_proven(self):
        _review, soak, qualification = security_qualification_schema_values()
        with self.assertRaisesRegex(ValueError, "24 hours"):
            replace(soak, status=EngineeringQualificationStatus.PASSED)
        with self.assertRaises(ValueError):
            replace(qualification, status=EngineeringQualificationStatus.PASSED)


if __name__ == "__main__":
    unittest.main()
