"""CLI for deliberate owner export of integration-network public authority."""

import argparse
import os
from pathlib import Path

from fam_os.product.network_authority_export import export_network_authority


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fam-network-authority")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--device-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = export_network_authority(
        args.output,
        identity_root=args.state_root / "fabric/identity",
        display_name=args.device_name, owner_uid=os.geteuid(),
    )
    print(result.root)
    print("key_id=" + result.key_id)


if __name__ == "__main__":
    main()
