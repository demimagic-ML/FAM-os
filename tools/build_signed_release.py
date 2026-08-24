#!/usr/bin/env python3
"""Build one portable signed complete FAM_OS release bundle."""

import argparse
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.product.release_assembly import CompleteReleaseAssembler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    key = load_pem_private_key(args.private_key.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("release key must be Ed25519")
    manifest = CompleteReleaseAssembler(args.repository).build(
        args.release_id, args.wheelhouse, args.output, args.key_id, key,
    )
    print(f"built {manifest.release_id} with {len(manifest.components)} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
