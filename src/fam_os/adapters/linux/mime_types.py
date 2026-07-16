"""Scoped MIME observation with bounded magic-database fallback."""

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.scoped_files import ScopedFilePolicy


_MIME = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


@dataclass(frozen=True, slots=True)
class MimeTypeEvidence:
    path: str
    mime_type: str
    source: str


class ScopedMimeTypeAdapter:
    def __init__(
        self, scope: ScopedFilePolicy, file_executable=Path("/usr/bin/file"), runner=None,
    ):
        if not file_executable.is_absolute():
            raise ValueError("MIME executable must be absolute")
        self._scope = scope
        self._executable = file_executable
        self._runner = runner or BoundedSubprocessRunner()

    def observe(self, path: Path) -> MimeTypeEvidence:
        path = self._scope.authorize(path)
        if not path.is_file():
            raise ValueError("MIME observation requires a regular file")
        try:
            result = self._runner.run(
                (str(self._executable), "--brief", "--mime-type", "--", str(path)),
                environment={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            )
        except Exception:
            result = None
        detected = result.stdout.strip() if result is not None and result.succeeded else ""
        if _MIME.fullmatch(detected):
            return MimeTypeEvidence(str(path), detected.lower(), "magic")
        guessed, _encoding = mimetypes.guess_type(path.name, strict=False)
        return MimeTypeEvidence(
            str(path), guessed or "application/octet-stream", "extension_fallback"
        )
