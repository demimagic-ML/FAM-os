"""Installed or source-tree runtime model catalog selection."""

from importlib import resources
from pathlib import Path

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.product.release_trust import verify_installed_release


def runtime_catalog(model_ref: str, source_root: Path | None) -> RuntimeModelCatalog:
    root = _release_root()
    if source_root is not None and (root / "release-manifest.json").is_file():
        return RuntimeModelCatalog.from_signed_release(
            root, root.parents[1] / "trust", source_root,
        )
    catalog = _configured_catalog(root, source_root)
    if catalog is not None:
        return catalog
    return RuntimeModelCatalog((RuntimeModelEntry(
        model_ref, "economical", tuple(ModelIntent), 1024**3, 8192, "0" * 64,
    ),))


def active_release_id() -> str:
    """Return the verified installed release identity or the source-tree label."""
    root = _release_root()
    if not (root / "release-manifest.json").is_file():
        return "development"
    return verify_installed_release(root, root.parents[1] / "trust").release_id


def active_release_root() -> Path:
    return Path(__file__).resolve().parents[4]


_release_root = active_release_root


def _configured_catalog(
    root: Path, source_root: Path | None,
) -> RuntimeModelCatalog | None:
    if source_root is None or not source_root.is_dir():
        return None
    candidates = (
        root / "share/expert/runtime/model-catalog.json",
        root / "configs/packages/runtime/model-catalog.json",
    )
    config = next((path for path in candidates if path.is_file()), None)
    if config is not None:
        catalog = RuntimeModelCatalog.from_source(config, source_root)
    else:
        packaged = resources.files("fam_os.product.resources").joinpath(
            "runtime", "model-catalog.json",
        )
        with resources.as_file(packaged) as packaged_config:
            catalog = RuntimeModelCatalog.from_source(packaged_config, source_root)
    return catalog if catalog.entries() else None
