"""Assemble every shipped FAM_OS component into deterministic archives."""

from __future__ import annotations

import tarfile
import tempfile
import subprocess
import shutil
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.release_bundle import (
    ReleaseBundleBuilder,
    ReleaseBundleInput,
)
from fam_os.product.update_contracts import ComponentKind, SignedReleaseManifest
from fam_os.product.vscode_package import VSIX_NAME, build_vscode_vsix
from fam_os.adapters.crypto.engineering_recipes import sign_recipe_specification
from fam_os.adapters.bubblewrap.engineering import toolchain_tree_sha256
from fam_os.adapters.crypto.documentation_recipes import (
    sign_documentation_recipe_specification,
)
from fam_os.adapters.crypto.review_recipes import (
    sign_engineering_reviewer_recipe_specification,
)
from fam_os.core.engineering import (
    EngineeringEcosystem, ToolRecipePurpose, ToolchainMount,
    ToolchainMountSourceKind,
)
from fam_os.core.engineering.production_recipes import (
    ToolRecipeSpecification, diagnostic_recipe_specifications,
    initial_recipe_specifications,
)
from fam_os.core.engineering.production_documentation_recipes import (
    initial_documentation_recipe_specifications,
)
from fam_os.core.engineering.production_review_recipes import (
    initial_engineering_reviewer_recipe_specification,
)
from fam_os.schemas import dumps_document


class CompleteReleaseAssembler:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def build(
        self,
        release_id: str,
        wheelhouse: Path,
        output: Path,
        key_id: str,
        private_key: Ed25519PrivateKey,
    ) -> SignedReleaseManifest:
        if wheelhouse.is_symlink() or not wheelhouse.is_dir():
            raise ValueError("complete release requires a wheelhouse directory")
        if not tuple(wheelhouse.glob("fam_os-*.whl")):
            raise ValueError("complete release wheelhouse is missing the FAM_OS wheel")
        _compile_connector(self._root / "connectors/vscode")
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            inputs = list(self._archives(
                staging, wheelhouse, key_id, private_key,
            ))
            return ReleaseBundleBuilder(key_id, private_key).build(
                release_id, tuple(inputs), output,
            )

    def _archives(
        self, staging: Path, wheelhouse: Path, key_id: str,
        private_key: Ed25519PrivateKey,
    ) -> tuple[ReleaseBundleInput, ...]:
        connector = staging / "connector"
        connector.mkdir()
        build_vscode_vsix(self._root / "connectors/vscode", connector / VSIX_NAME)
        package_source = staging / "package-config"
        shutil.copytree(self._root / "configs/packages", package_source)
        _write_release_recipes(
            package_source, key_id, private_key,
            self._root / "src/fam_os/adapters/diagnostics/tool.py",
        )
        specs = (
            (ComponentKind.SERVICE, "wheelhouse.tar", wheelhouse, _wheel_file),
            (ComponentKind.SCHEMA, "schemas.tar", self._root / "schemas", None),
            (ComponentKind.EXPERT, "experts.tar", package_source, None),
            (
                ComponentKind.CONNECTOR, "vscode.tar", connector, None,
            ),
            (
                ComponentKind.CONSOLE, "console.tar",
                self._root / "src/fam_os/console/static", None,
            ),
            (
                ComponentKind.SERVICE_UNIT, "systemd.tar",
                self._root / "packaging/systemd", None,
            ),
            (
                ComponentKind.MIGRATION, "migrations.tar",
                self._root / "src/fam_os/product/storage/migrations", _migration_file,
            ),
        )
        values = []
        for kind, name, source, predicate in specs:
            target = staging / name
            _deterministic_tar(source, target, predicate)
            values.append(ReleaseBundleInput(kind, name, target))
        return tuple(values)


def _deterministic_tar(source: Path, target: Path, predicate=None) -> None:
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"release archive source is invalid: {source}")
    files = tuple(
        path for path in sorted(source.rglob("*"))
        if path.is_file() and not path.is_symlink()
        and (predicate is None or predicate(path.relative_to(source)))
    )
    if not files:
        raise ValueError(f"release archive source is empty: {source}")
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            info = archive.gettarinfo(str(path), str(path.relative_to(source)))
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as stream:
                archive.addfile(info, stream)


def _migration_file(relative: Path) -> bool:
    return relative.suffix == ".sql"


def _wheel_file(relative: Path) -> bool:
    return relative.suffix == ".whl" and len(relative.parts) == 1


def _write_release_recipes(
    root, key_id, private_key, diagnostic_tool_source: Path,
) -> None:
    integration = root / "integration-recipes"
    integration.mkdir(parents=True, exist_ok=False)
    specification = ToolRecipeSpecification(
        EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
        "/usr/bin/python3",
        ("/workspace/.fam/services/api.py", "{port:api}"),
        "integration.http.health.v1",
    )
    recipe = sign_recipe_specification(specification, key_id, private_key)
    (integration / "python-http.json").write_text(
        dumps_document(recipe) + "\n", encoding="utf-8",
    )
    static_preview = sign_recipe_specification(
        ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
            "/usr/bin/python3",
            (
                "-m", "http.server", "{port:preview}", "--bind",
                "127.0.0.1", "--directory", "/workspace",
            ),
            "integration.static-http.health.v1",
            "integration.python.static-http",
        ),
        key_id,
        private_key,
    )
    (integration / "python-static-http.json").write_text(
        dumps_document(static_preview) + "\n", encoding="utf-8",
    )
    root_api = sign_recipe_specification(
        ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
            "/usr/bin/python3", ("/workspace/api.py", "{port:api}"),
            "integration.root-api.health.v1", "integration.python.root-api",
        ),
        key_id,
        private_key,
    )
    (integration / "python-root-api.json").write_text(
        dumps_document(root_api) + "\n", encoding="utf-8",
    )
    engineering = root / "engineering-recipes"
    engineering.mkdir(parents=True, exist_ok=False)
    diagnostic_tool = root / "toolchains/diagnostics/tool.py"
    diagnostic_tool.parent.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(diagnostic_tool_source, diagnostic_tool)
    diagnostic_mount = ToolchainMount(
        "share/expert/toolchains/diagnostics/tool.py",
        "/opt/fam/toolchains/diagnostics/tool.py",
        toolchain_tree_sha256(diagnostic_tool),
        ToolchainMountSourceKind.INSTALLED_RELEASE,
    )
    specifications = (
        *initial_recipe_specifications(), *diagnostic_recipe_specifications(),
    )
    for item in specifications:
        mounts = (
            (diagnostic_mount,)
            if "/opt/fam/toolchains/diagnostics/tool.py" in item.argv
            else ()
        )
        signed = sign_recipe_specification(
            item, key_id, private_key, toolchain_mounts=mounts,
        )
        name = f"{item.ecosystem.value}-{item.purpose.value}.json"
        (engineering / name).write_text(
            dumps_document(signed) + "\n", encoding="utf-8",
        )
    documentation = root / "documentation-recipes"
    documentation.mkdir(parents=True, exist_ok=False)
    for item in initial_documentation_recipe_specifications():
        signed = sign_documentation_recipe_specification(
            item, key_id, private_key,
        )
        (documentation / f"{item.kind.value}.json").write_text(
            dumps_document(signed) + "\n", encoding="utf-8",
        )
    reviews = root / "review-recipes"
    reviews.mkdir(parents=True, exist_ok=False)
    reviewer = sign_engineering_reviewer_recipe_specification(
        initial_engineering_reviewer_recipe_specification(),
        key_id, private_key,
    )
    (reviews / "independent.json").write_text(
        dumps_document(reviewer) + "\n", encoding="utf-8",
    )


def _compile_connector(source: Path) -> None:
    try:
        subprocess.run(
            ("npm", "run", "compile"), cwd=source, check=True,
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("VS Code connector compilation failed") from error
