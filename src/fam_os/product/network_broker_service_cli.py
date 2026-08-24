"""Root-only entrypoint from an independently verified signed installation."""

import argparse
import os
from pathlib import Path

from fam_os.adapters.integration.network_broker_cli import main as run_broker
from fam_os.product.bundle_installation import SignedBundleInstallation


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--installation-prefix", type=Path, required=True)
    args, remaining = parser.parse_known_args(argv)
    _require_root_installation(args.installation_prefix, os.geteuid())
    run_broker(remaining)


def _require_root_installation(prefix, effective_uid, installation_factory=None):
    if effective_uid != 0:
        raise PermissionError("integration network broker requires host administrator")
    if not prefix.is_absolute() or prefix.is_symlink():
        raise PermissionError("network broker installation prefix is invalid")
    factory = installation_factory or SignedBundleInstallation
    receipt = factory(prefix, {}).diagnose()
    if not receipt.healthy:
        raise PermissionError(
            "network broker signed root installation is unhealthy: "
            + ",".join(receipt.issues)
        )
