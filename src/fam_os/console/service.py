"""Secure local Console service composition."""

from __future__ import annotations

import argparse
import os
import secrets
import stat
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider


def load_or_create_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    if path.exists():
        details = path.stat(follow_symlinks=False)
        if path.is_symlink() or details.st_uid != os.geteuid():
            raise PermissionError("console token must be an owner file")
        if stat.S_IMODE(details.st_mode) != 0o600:
            raise PermissionError("console token must use mode 0600")
        token = path.read_text().strip()
        if len(token) < 32:
            raise ValueError("stored console token is invalid")
        return token
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    token = secrets.token_urlsafe(32)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(token + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return token


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FAM Console local service")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--release-id", default="development")
    args = parser.parse_args(argv)
    args.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = load_or_create_token(args.token_file)
    server = ConsoleHttpServer(
        ("127.0.0.1", args.port),
        LocalConsoleProvider(args.state_root, args.release_id), token,
    )
    print(f"FAM Console: http://127.0.0.1:{server.server_port}/#token={token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
