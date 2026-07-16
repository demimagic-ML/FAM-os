"""Small Linux product-lifecycle command dispatcher."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from fam_os.product.linux_installation import LinuxInstallation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fam-os")
    parser.add_argument("--prefix", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        command = commands.add_parser(name)
        command.add_argument("--source-package", type=Path, required=True)
        command.add_argument("--release-id", required=True)
    commands.add_parser("diagnose")
    repair = commands.add_parser("repair")
    repair.add_argument("--source-package", type=Path, required=True)
    commands.add_parser("remove")
    args = parser.parse_args(argv)
    installation = LinuxInstallation(args.prefix.absolute())
    if args.command in {"install", "update"}:
        receipt = getattr(installation, args.command)(args.source_package, args.release_id)
    elif args.command == "repair":
        receipt = installation.repair(args.source_package)
    elif args.command == "diagnose":
        receipt = installation.diagnose()
    else:
        installation.remove()
        print(json.dumps({"removed": True, "prefix": str(args.prefix)}))
        return 0
    print(json.dumps(asdict(receipt), sort_keys=True))
    return 0 if receipt.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
