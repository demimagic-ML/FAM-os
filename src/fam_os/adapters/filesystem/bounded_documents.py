"""No-follow bounded UTF-8 reads shared by strict document sources."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def read_bounded_regular_utf8(path: Path, limit: int) -> str:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("document source entry is not a regular file")
        if metadata.st_size > limit:
            raise ValueError("document exceeds byte limit")
        content = os.read(descriptor, limit + 1)
        if len(content) > limit:
            raise ValueError("document exceeds byte limit")
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("document is not UTF-8") from error
    finally:
        os.close(descriptor)
