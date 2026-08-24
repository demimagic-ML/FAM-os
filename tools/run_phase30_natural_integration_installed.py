#!/usr/bin/python3
"""Qualify natural integration composition from one installed signed release."""

import argparse
import json
from pathlib import Path
import sys
import unittest


TEST_MODULES = (
    "tests.unit.test_natural_integration_environment",
    "tests.integration.test_natural_integration_environment",
    "tests.integration.test_natural_multi_service_process",
    "tests.integration.test_natural_postgresql_environment",
    "tests.unit.test_natural_postgresql_planning",
    "tests.unit.test_postgresql_verification_service",
    "tests.unit.test_docker_command_client_input",
    "tests.unit.test_candidate_generation_service",
    "tests.unit.test_candidate_changeset_service",
    "tests.unit.test_integration_environment_service",
    "tests.unit.test_integration_environment_repository",
    "tests.unit.test_product_integration_environment_api",
    "tests.unit.test_process_integration_environment",
    "tests.unit.test_master_engineering_loop",
    "tests.unit.test_product_engineering_loop_api",
    "tests.unit.test_product_natural_engineering_api",
    "tests.unit.test_release_bundle",
    "tests.unit.test_installed_integration_recipes",
    "tests.contract.test_schema_roundtrip",
    "tests.contract.test_schema_compatibility",
    "tests.unit.test_fam_shell_engineering_loop_transport",
    "tests.integration.test_console_engineering_loop",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--expected-schemas", type=int, required=True)
    args = parser.parse_args()
    installed = args.installed_root.resolve(strict=True)
    repository = args.repository.resolve(strict=True)
    installed_python = installed / "python"
    if not installed_python.is_dir() or installed_python.is_symlink():
        raise PermissionError("installed Python root is unavailable or unsafe")
    sys.path.insert(0, str(repository))
    sys.path.insert(0, str(installed_python))

    import fam_os
    from fam_os.product.composition.integration_recipes import (
        installed_integration_recipe_catalog,
    )
    from fam_os.schemas import SCHEMA_DESCRIPTORS

    module = Path(fam_os.__file__).resolve(strict=True)
    if not module.is_relative_to(installed_python):
        raise RuntimeError(f"checkout import leakage: {module}")
    catalog = installed_integration_recipe_catalog(installed)
    if catalog is None:
        raise RuntimeError("installed integration recipe catalog is absent")
    recipes = {
        identity: catalog.get(identity, "1.0.0")
        for identity in (
            "integration.python.root-api",
            "integration.python.static-http",
        )
    }
    if len(SCHEMA_DESCRIPTORS) != args.expected_schemas:
        raise RuntimeError(
            f"unexpected installed schema count: {len(SCHEMA_DESCRIPTORS)}"
        )

    print(json.dumps({
        "installed_module": str(module),
        "schema_count": len(SCHEMA_DESCRIPTORS),
        "recipe_coordinates": sorted(
            f"{item.recipe_id}@{item.recipe_version}"
            for item in recipes.values()
        ),
    }, sort_keys=True))
    suite = unittest.TestLoader().loadTestsFromNames(TEST_MODULES)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
