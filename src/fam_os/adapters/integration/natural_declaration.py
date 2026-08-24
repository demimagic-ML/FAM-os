"""Bounded strict loading of candidate natural-integration declarations."""

from pathlib import Path

from fam_os.adapters.filesystem.candidate_io import read_regular
from fam_os.core.engineering import (
    NATURAL_INTEGRATION_DECLARATION_PATH,
    NaturalIntegrationEnvironmentDeclaration,
)
from fam_os.schemas import loads_document


MAXIMUM_DECLARATION_BYTES = 65_536


def load_natural_integration_declaration(
    candidate_root: Path,
) -> NaturalIntegrationEnvironmentDeclaration | None:
    path = candidate_root / NATURAL_INTEGRATION_DECLARATION_PATH
    if not path.exists():
        return None
    try:
        serialized = read_regular(path, MAXIMUM_DECLARATION_BYTES).decode(
            "utf-8", "strict",
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(
            "natural integration declaration is not a bounded UTF-8 regular file"
        ) from error
    value = loads_document(serialized)
    if not isinstance(value, NaturalIntegrationEnvironmentDeclaration):
        raise TypeError("natural integration declaration has the wrong schema")
    return value
