"""Invariant tests for owner-delegated engineering contracts."""

from dataclasses import replace
from datetime import timedelta
import unittest

from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringOperation,
    EngineeringResultKind,
    FileOperation,
    FileOperationKind,
    GitOperationKind,
)
from tests.contract.schema_engineering_fixtures import (
    DIGEST_A,
    DIGEST_B,
    engineering_schema_values,
    engineering_result_schema_values,
)


class EngineeringContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.task, self.snapshot, self.operation, self.proposal, self.recipe,
            self.run, self.dependency, self.design, self.git, self.checkpoint,
            self.evidence,
        ) = engineering_schema_values()

    def test_owner_may_explicitly_delegate_every_engineering_authority(self) -> None:
        task = replace(self.task, authorities=tuple(EngineeringAuthority))
        self.assertEqual(set(task.authorities), set(EngineeringAuthority))
        self.assertIn(EngineeringAuthority.RAW_SHELL, task.authorities)
        self.assertIn(EngineeringAuthority.HOST_ADMIN, task.authorities)
        self.assertIn(EngineeringAuthority.SELF_UPDATE, task.authorities)

    def test_observation_does_not_imply_modification(self) -> None:
        with self.assertRaisesRegex(ValueError, "modify authority"):
            replace(
                self.task,
                authorities=(EngineeringAuthority.OBSERVE,),
                permitted_operations=(EngineeringOperation.CREATE,),
                network_hosts=(),
                package_registries=(),
            )

    def test_execution_and_network_are_separate_authorities(self) -> None:
        with self.assertRaisesRegex(ValueError, "network authority"):
            replace(
                self.recipe,
                network_required=True,
                required_authorities=(EngineeringAuthority.EXECUTE,),
            )

    def test_publish_is_not_implied_by_git_modification(self) -> None:
        with self.assertRaisesRegex(ValueError, "publish authority"):
            replace(
                self.git,
                kind=GitOperationKind.PUSH,
                required_authorities=(EngineeringAuthority.MODIFY,),
            )

    def test_forced_git_effect_requires_protected_ref_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "protected-ref authority"):
            replace(self.git, force=True)

    def test_task_expiry_and_workspace_roots_are_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "later than"):
            replace(self.task, expires_at=self.task.created_at - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "absolute normalized"):
            replace(self.task, workspace_roots=("relative/workspace",))

    def test_file_operations_are_compare_and_swap_proposals(self) -> None:
        with self.assertRaisesRegex(ValueError, "replace requires"):
            FileOperation(
                "operation-2", FileOperationKind.REPLACE, "src/new.py", None,
                DIGEST_B, None, True,
            )
        with self.assertRaisesRegex(ValueError, "create requires"):
            FileOperation(
                "operation-3", FileOperationKind.CREATE, "src/new.py", DIGEST_A,
                DIGEST_B, None, True,
            )

    def test_success_cannot_hide_unresolved_risks(self) -> None:
        with self.assertRaisesRegex(ValueError, "unresolved risks"):
            replace(self.evidence, unresolved_risks=("untested migration",))

    def test_result_kinds_are_not_model_relabelable(self) -> None:
        proposal, receipt, publication, published, unavailable = (
            engineering_result_schema_values()
        )
        cases = (
            (proposal, EngineeringResultKind.PUBLICATION_RECEIPT),
            (receipt, EngineeringResultKind.CHANGESET_PROPOSAL),
            (publication, EngineeringResultKind.CAPABILITY_UNAVAILABLE),
            (published, EngineeringResultKind.VERIFIED_CHANGESET_RECEIPT),
            (unavailable, EngineeringResultKind.PUBLICATION_PROPOSAL),
        )
        for value, wrong_kind in cases:
            with self.subTest(root_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "result_kind must be"):
                    replace(value, result_kind=wrong_kind)

    def test_verified_change_receipt_requires_independent_evidence(self) -> None:
        _proposal, receipt, _publication, _published, _unavailable = (
            engineering_result_schema_values()
        )
        with self.assertRaisesRegex(ValueError, "verifier_run_ids"):
            replace(receipt, verifier_run_ids=())
        with self.assertRaisesRegex(ValueError, "changed workspace tree"):
            replace(receipt, after_tree_sha256=receipt.before_tree_sha256)

    def test_publication_receipt_requires_postcondition_verification(self) -> None:
        _proposal, _receipt, _publication, published, _unavailable = (
            engineering_result_schema_values()
        )
        with self.assertRaisesRegex(ValueError, "postcondition verification"):
            replace(published, verifier_run_ids=())


if __name__ == "__main__":
    unittest.main()
