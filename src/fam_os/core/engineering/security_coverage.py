"""Trusted installed adversarial coverage ledger for engineering authority."""

from fam_os.core.engineering.security_qualification import ADVERSARIAL_CATEGORIES


ENGINEERING_ADVERSARIAL_TESTS = {
    "repository_prompt_injection": "tests.unit.test_repository_intelligence.RepositoryIntelligenceTests.test_repository_instructions_comments_and_metadata_remain_untrusted_context",
    "malicious_build_file": "tests.unit.test_engineering_execution.EngineeringExecutionTests.test_signed_recipe_rejects_semantic_tampering",
    "package_name_confusion": "tests.unit.test_engineering_execution.EngineeringExecutionTests.test_dependency_adapter_stages_artifacts_and_records_lock_sbom_and_network",
    "compromised_registry": "tests.unit.test_engineering_execution.EngineeringExecutionTests.test_dependency_admission_is_project_local_budgeted_and_supply_chain_checked",
    "symlink_race": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_candidate_rejects_symlink_and_hardlink_races",
    "hardlink_race": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_candidate_rejects_symlink_and_hardlink_races",
    "archive_traversal": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_release_archive_rejects_traversal_links_and_devices",
    "fork_bomb": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_network_exfiltration_output_flood_and_fork_pressure_are_contained",
    "output_flood": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_network_exfiltration_output_flood_and_fork_pressure_are_contained",
    "secret_discovery": "tests.unit.test_engineering_execution.EngineeringExecutionTests.test_candidate_sandbox_has_no_network_home_credentials_or_git_hooks",
    "data_exfiltration": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_network_exfiltration_output_flood_and_fork_pressure_are_contained",
    "malicious_svg_media": "tests.security.test_engineering_adversarial.EngineeringAdversarialTests.test_malicious_svg_external_content_and_decompression_bomb_fail_closed",
    "git_hook_execution": "tests.unit.test_git_delivery.GitDeliveryTests.test_local_branch_exact_stage_commit_observe_blame_and_restore",
    "submodule_escape": "tests.unit.test_git_delivery.GitDeliveryTests.test_local_git_rejects_metadata_and_nested_repository_paths",
    "stale_approval": "tests.unit.test_candidate_workspace.CandidateWorkspaceTests.test_stale_baseline_rejects_entire_transaction_before_apply",
    "restart_replay": "tests.unit.test_git_delivery.GitDeliveryTests.test_publication_consumption_survives_restart",
}


def validate_adversarial_coverage() -> None:
    if set(ENGINEERING_ADVERSARIAL_TESTS) != ADVERSARIAL_CATEGORIES:
        raise RuntimeError("engineering adversarial coverage ledger is incomplete")
    if any(not value.startswith("tests.") for value in ENGINEERING_ADVERSARIAL_TESTS.values()):
        raise RuntimeError("engineering adversarial coverage requires exact test identities")
