"""Intent-subordinate selection of fixed natural integration templates."""

from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote

from fam_os.adapters.integration.natural_declaration import (
    load_natural_integration_declaration,
)
from fam_os.core.engineering import (
    NaturalIntegrationEnvironmentDeclaration,
    NaturalIntegrationServiceDeclaration,
    NaturalIntegrationServiceTemplate,
)


_API_REQUEST = re.compile(r"\b(api|backend|full[- ]?stack|web service)\b")
_STATIC_REQUEST = re.compile(
    r"\b(full[- ]?stack|site|web app|page|browser preview)\b"
)
_POSTGRESQL_REQUEST = re.compile(
    r"\b(?:postgresql|postgres)\s+(?:service|container)|"
    r"\b(?:run|start|launch|test)\s+(?:a\s+|the\s+)?"
    r"(?:postgresql|postgres)(?:\s+(?:service|container|database))?\b",
)


def natural_integration_templates(definition, candidate, changed_paths):
    root = Path(candidate.candidate_workspace)
    normalized = " ".join(definition.task.intent.casefold().split())
    api_requested = _API_REQUEST.search(normalized) is not None
    static_requested = _STATIC_REQUEST.search(normalized) is not None
    postgresql_requested = _POSTGRESQL_REQUEST.search(normalized) is not None
    health_path = _optional_health_path(root, candidate, changed_paths)
    declaration = load_natural_integration_declaration(root)
    if declaration is None:
        declaration = _implicit_declaration(
            api_requested, static_requested, postgresql_requested, health_path,
        )
    templates = {item.template for item in declaration.services}
    if (
        NaturalIntegrationServiceTemplate.PYTHON_API in templates
        and not api_requested
    ):
        raise PermissionError(
            "natural API declaration exceeds the admitted request intent"
        )
    if (
        api_requested
        and NaturalIntegrationServiceTemplate.PYTHON_API not in templates
    ):
        raise LookupError(
            "explicit natural API integration requires a Python API service"
        )
    if (
        NaturalIntegrationServiceTemplate.STATIC_SITE in templates
        and api_requested and not static_requested
    ):
        raise PermissionError(
            "natural static declaration exceeds the admitted request intent"
        )
    if (
        static_requested
        and NaturalIntegrationServiceTemplate.STATIC_SITE not in templates
    ):
        raise LookupError(
            "explicit natural site integration requires a static service"
        )
    if (
        NaturalIntegrationServiceTemplate.POSTGRESQL in templates
        and not postgresql_requested
    ):
        raise PermissionError(
            "natural PostgreSQL declaration exceeds the admitted request intent"
        )
    if (
        postgresql_requested
        and NaturalIntegrationServiceTemplate.POSTGRESQL not in templates
    ):
        raise LookupError(
            "explicit natural PostgreSQL integration requires a PostgreSQL service"
        )
    if (
        NaturalIntegrationServiceTemplate.PYTHON_API in templates
        and not _regular(root, "api.py")
    ):
        raise LookupError(
            "natural API integration requires a regular root api.py"
        )
    if (
        NaturalIntegrationServiceTemplate.STATIC_SITE in templates
        and health_path is None
    ):
        raise LookupError(
            "natural static integration requires a regular candidate HTML file"
        )
    values = tuple(
        (
            item,
            (
                "/health"
                if item.template is NaturalIntegrationServiceTemplate.PYTHON_API
                else (
                    None
                    if item.template is NaturalIntegrationServiceTemplate.POSTGRESQL
                    else health_path
                )
            ),
        )
        for item in declaration.services
    )
    if not values:
        raise LookupError(
            "natural integration requires a regular candidate HTML file "
            "or an explicitly requested root api.py"
        )
    return values


def _optional_health_path(root, candidate, changed_paths):
    try:
        return _health_path(root, candidate, changed_paths)
    except LookupError:
        return None


def _health_path(root: Path, candidate, changed_paths: tuple[str, ...]) -> str:
    paths = tuple(dict.fromkeys((
        *changed_paths,
        *(entry.path for entry in candidate.entries),
    )))
    html = []
    for relative in paths:
        value = PurePosixPath(relative)
        if (
            value.is_absolute() or ".." in value.parts
            or value.suffix.casefold() != ".html"
        ):
            continue
        target = root.joinpath(*value.parts)
        if (
            target.is_file() and not target.is_symlink()
            and target.resolve().is_relative_to(root)
        ):
            html.append(value.as_posix())
    if not html:
        raise LookupError(
            "natural static preview requires a regular candidate HTML file"
        )
    selected = "index.html" if "index.html" in html else sorted(html)[0]
    return "/" + quote(selected, safe="/._-")


def _regular(root: Path, relative: str) -> bool:
    target = root / relative
    return (
        target.is_file() and not target.is_symlink()
        and target.resolve().is_relative_to(root)
    )


def _implicit_declaration(
    api_requested, static_requested, postgresql_requested, health_path,
):
    services = []
    if postgresql_requested:
        services.append(NaturalIntegrationServiceDeclaration(
            "postgresql", NaturalIntegrationServiceTemplate.POSTGRESQL, (),
        ))
    if api_requested:
        services.append(NaturalIntegrationServiceDeclaration(
            "python-api", NaturalIntegrationServiceTemplate.PYTHON_API,
            (("postgresql",) if postgresql_requested else ()),
        ))
    if health_path is not None and (static_requested or not api_requested):
        services.append(NaturalIntegrationServiceDeclaration(
            "static-preview", NaturalIntegrationServiceTemplate.STATIC_SITE,
            (("python-api",) if api_requested else ()),
        ))
    if not services:
        raise LookupError(
            "natural integration requires a regular candidate HTML file "
            "or an explicitly requested root api.py"
        )
    return NaturalIntegrationEnvironmentDeclaration(
        "implicit-natural-integration", tuple(services),
    )
