"""Deterministic VSIX construction and safe extraction."""

import json
import zipfile
from pathlib import Path


VSIX_NAME = "fam-os-vscode-connector.vsix"


def build_vscode_vsix(source: Path, target: Path) -> None:
    package = json.loads((source / "package.json").read_text(encoding="utf-8"))
    if (package.get("publisher"), package.get("name")) != (
        "fam-os", "fam-os-vscode-connector",
    ):
        raise ValueError("VS Code connector package identity is invalid")
    files = tuple(
        path for path in sorted(source.rglob("*"))
        if path.is_file() and not path.is_symlink()
        and (
            path.relative_to(source).parts[0] in {"out", "schemas"}
            or path.name in {"package.json", "README.md"}
        )
    )
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        _write(archive, "[Content_Types].xml", _content_types())
        _write(archive, "extension.vsixmanifest", _manifest(package))
        for path in files:
            _write(archive, f"extension/{path.relative_to(source)}", path.read_bytes())


def extract_vscode_vsix(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source) as archive:
        members = tuple(item for item in archive.infolist() if not item.is_dir())
        for member in members:
            path = Path(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("VSIX contains an unsafe path")
            if not path.parts or path.parts[0] != "extension":
                continue
            relative = Path(*path.parts[1:])
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))


def _write(archive, name: str, content: str | bytes) -> None:
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content.encode("utf-8") if isinstance(content, str) else content)


def _content_types() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="json" ContentType="application/json"/>'
        '<Default Extension="js" ContentType="application/javascript"/>'
        '<Default Extension="md" ContentType="text/markdown"/>'
        '<Default Extension="vsixmanifest" ContentType="text/xml"/>'
        '</Types>'
    )


def _manifest(package) -> str:
    version = package.get("version")
    if not isinstance(version, str):
        raise ValueError("VS Code connector version is invalid")
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<PackageManifest Version="2.0.0" '
        'xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">'
        '<Metadata><Identity Id="fam-os-vscode-connector" Version="'
        f'{version}" Publisher="fam-os" Language="en-US"/>'
        '<DisplayName>FAM_OS Semantic Connector</DisplayName>'
        '<Description xml:space="preserve">Local semantic Application Fabric connector.</Description>'
        '<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" '
        'Version="[1.110.0,)"/></Installation></Metadata>'
        '<Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" '
        'Path="extension/package.json" Addressable="true"/></Assets>'
        '</PackageManifest>'
    )
