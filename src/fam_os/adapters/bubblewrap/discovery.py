"""Injectable executable discovery."""

import shutil
from typing import Protocol


class ExecutableLocator(Protocol):
    def find(self, executable: str) -> str | None: ...


class PathExecutableLocator:
    def find(self, executable: str) -> str | None:
        return shutil.which(executable)
