"""Small Linux product-lifecycle command dispatcher."""

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.removal import CompleteProductRemoval
from fam_os.product.vscode_installation import VsCodeConnectorInstallation
from fam_os.product.console_cli import run_console_command
from fam_os.adapters.mcp.ingress import run_mcp_ingress_stdio
from fam_os.product.peer_cli import run_peer_command
from fam_os.product.factory_runtime_configuration import (
    FactoryRuntimeConfiguration,
    FactoryRuntimeConfigurationStore,
)
from fam_os.product.host_security import diagnose_verifier_sandbox


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fam-os")
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument(
        "--trusted-key", action="append", default=[], metavar="KEY_ID=PUBLIC_KEY_PEM",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        command = commands.add_parser(name)
        command.add_argument("--bundle", type=Path, required=True)
    commands.add_parser("diagnose")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--release-id", required=True)
    commands.add_parser("enable")
    commands.add_parser("disable")
    commands.add_parser("repair")
    remove = commands.add_parser("remove")
    remove.add_argument("--state-root", type=Path, default=_state_root())
    remove.add_argument("--runtime-root", type=Path, default=_runtime_root())
    remove.add_argument(
        "--extension-root", type=Path,
        default=Path.home() / ".vscode/extensions",
    )
    remove.add_argument("--confirm", action="store_true")
    host_security = commands.add_parser("host-security")
    host_security.add_argument("action", choices=("diagnose",))
    console = commands.add_parser("console")
    console.add_argument("--runtime-root", type=Path)
    console.add_argument("--port", type=int, default=8765)
    connector = commands.add_parser("connector")
    connector.add_argument("action", choices=("install", "update", "status", "remove"))
    connector.add_argument("kind", choices=("vscode",))
    connector.add_argument(
        "--extension-root", type=Path,
        default=Path.home() / ".vscode/extensions",
    )
    mcp = commands.add_parser("mcp")
    mcp.add_argument("action", choices=("serve",))
    mcp.add_argument("--client-id", required=True)
    mcp.add_argument("--runtime-root", type=Path, default=_runtime_root())
    peer = commands.add_parser("peer")
    peer.add_argument("--state-root", type=Path, default=_state_root())
    peer.add_argument("--device-name")
    peer_commands = peer.add_subparsers(dest="peer_action", required=True)
    peer_commands.add_parser("identity")
    offer = peer_commands.add_parser("offer")
    offer.add_argument("--host")
    offer.add_argument("--port", type=int)
    configure = peer_commands.add_parser("configure")
    configure.add_argument("--listen-host", required=True)
    configure.add_argument("--listen-port", required=True, type=int)
    configure.add_argument("--advertised-host", required=True)
    configure.add_argument("--advertised-port", required=True, type=int)
    configure.add_argument("--confirm", action="store_true")
    code = peer_commands.add_parser("code")
    _pairing_inputs(code)
    approve = peer_commands.add_parser("approve")
    _pairing_inputs(approve)
    approve.add_argument("--code", required=True)
    approve.add_argument("--confirm", action="store_true")
    factory = commands.add_parser("factory")
    factory.add_argument("--state-root", type=Path, default=_state_root())
    factory_commands = factory.add_subparsers(
        dest="factory_action", required=True,
    )
    factory_commands.add_parser("status")
    factory_disable = factory_commands.add_parser("disable")
    factory_disable.add_argument("--confirm", action="store_true")
    factory_configure = factory_commands.add_parser("configure")
    _factory_runtime_inputs(factory_configure)
    factory_configure.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "mcp":
        if not (args.prefix.absolute() / "active").is_dir():
            raise RuntimeError("signed FAM_OS installation is not active")
        asyncio.run(run_mcp_ingress_stdio(
            args.runtime_root.absolute() / "mcp-ingress.sock", args.client_id,
        ))
        return 0
    installation = SignedBundleInstallation(
        args.prefix.absolute(), _trusted_keys(args.trusted_key),
    )
    if args.command == "console":
        diagnosis = installation.diagnose()
        if not diagnosis.healthy:
            raise RuntimeError("signed FAM_OS installation is not healthy")
        runtime_root = args.runtime_root or _runtime_root(args.prefix)
        return run_console_command(runtime_root, args.port)
    if args.command == "host-security":
        diagnosis = installation.diagnose()
        if not diagnosis.healthy:
            raise RuntimeError("signed FAM_OS installation is not healthy")
        sandbox_receipt = diagnose_verifier_sandbox()
        print(json.dumps(asdict(sandbox_receipt), sort_keys=True))
        return 0 if sandbox_receipt.healthy else 1
    if args.command == "peer":
        diagnosis = installation.diagnose()
        if not diagnosis.healthy:
            raise RuntimeError("signed FAM_OS installation is not healthy")
        return run_peer_command(args)
    if args.command == "factory":
        diagnosis = installation.diagnose()
        if not diagnosis.healthy:
            raise RuntimeError("signed FAM_OS installation is not healthy")
        return _run_factory_configuration(args)
    if args.command in {"install", "update"}:
        receipt = getattr(installation, args.command)(args.bundle.absolute())
    elif args.command == "rollback":
        receipt = installation.rollback(args.release_id)
    elif args.command == "diagnose":
        receipt = installation.diagnose()
    elif args.command == "repair":
        receipt = installation.repair()
    elif args.command == "connector":
        diagnosis = installation.diagnose()
        if not diagnosis.healthy:
            raise RuntimeError("signed installation is not healthy")
        connector_manager = VsCodeConnectorInstallation(
            args.prefix.absolute() / "active", args.extension_root.absolute(),
        )
        operation = args.action
        receipt = getattr(connector_manager, operation)()
        print(json.dumps(asdict(receipt), sort_keys=True))
        return 0 if operation == "remove" or receipt.installed else 1
    elif args.command in {"enable", "disable"}:
        units = Path.home() / ".config/systemd/user"
        if args.command == "enable":
            installation.install_user_unit(units)
            _systemctl("daemon-reload")
            _systemctl("enable", "--now", "fam-os.service")
        else:
            _systemctl("disable", "--now", "fam-os.service", check=False)
            installation.remove_user_unit(units)
            _systemctl("daemon-reload")
        print(json.dumps({args.command + "d": True, "unit_root": str(units)}))
        return 0
    elif args.command == "remove":
        connector_manager = VsCodeConnectorInstallation(
            args.prefix.absolute() / "active", args.extension_root.absolute(),
        )
        removal = CompleteProductRemoval(
            installation, connector_manager,
            args.state_root.absolute(), args.runtime_root.absolute(),
            Path.home() / ".config/systemd/user", _systemctl,
        )
        removal_receipt = removal.remove(confirmed=args.confirm)
        print(json.dumps(asdict(removal_receipt), sort_keys=True))
        return 0
    else:
        raise RuntimeError("unsupported FAM_OS lifecycle command")
    print(json.dumps(asdict(receipt), sort_keys=True))
    return 0 if receipt.healthy else 1


def _trusted_keys(values: list[str]) -> dict[str, Ed25519PublicKey]:
    keys = {}
    for value in values:
        key_id, separator, path = value.partition("=")
        if not separator or not key_id or key_id in keys:
            raise ValueError("trusted keys must use unique KEY_ID=PATH values")
        key = load_pem_public_key(Path(path).read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("trusted release keys must be Ed25519")
        keys[key_id] = key
    return keys


def _systemctl(*arguments: str, check: bool = True) -> None:
    subprocess.run(
        ("systemctl", "--user", *arguments), check=check,
        capture_output=True, text=True, timeout=30,
    )


def _runtime_root(prefix: Path | None = None) -> Path:
    name = "fam-os" if prefix is None else prefix.absolute().name or "fam-os"
    return (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}"))
        / name
    )


def _state_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "fam-os"


def _pairing_inputs(parser) -> None:
    parser.add_argument("--local-offer", required=True, type=Path)
    parser.add_argument("--peer-offer", required=True, type=Path)


def _factory_runtime_inputs(parser) -> None:
    parser.add_argument("--training-environment-directory", type=Path, required=True)
    parser.add_argument("--training-wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--training-model-directory", type=Path, required=True)
    parser.add_argument("--evaluation-suite", type=Path, required=True)
    parser.add_argument("--conversion-environment-directory", type=Path, required=True)
    parser.add_argument("--conversion-wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--llama-cpp-directory", type=Path, required=True)
    parser.add_argument("--llama-cpp-revision", required=True)
    parser.add_argument("--conversion-model-directory", type=Path, required=True)
    parser.add_argument("--canary-suite", type=Path, required=True)
    parser.add_argument(
        "--allowed-license", action="append", dest="allowed_licenses",
        required=True,
    )


def _run_factory_configuration(args) -> int:
    store = FactoryRuntimeConfigurationStore(
        args.state_root.absolute() / "config/factory-runtime.json",
        os.geteuid(),
    )
    if args.factory_action == "status":
        configuration = store.load()
        print(json.dumps({
            "configured": configuration is not None,
            "configuration": (
                None if configuration is None else asdict(configuration)
            ),
        }, sort_keys=True))
        return 0
    if not args.confirm:
        raise PermissionError("factory runtime configuration requires confirmation")
    if args.factory_action == "disable":
        print(json.dumps({"removed": store.remove()}, sort_keys=True))
        return 0
    configuration = FactoryRuntimeConfiguration(
        training_environment_directory=str(
            args.training_environment_directory.absolute()
        ),
        training_wheelhouse_manifest=str(
            args.training_wheelhouse_manifest.absolute()
        ),
        training_model_directory=str(args.training_model_directory.absolute()),
        evaluation_suite=str(args.evaluation_suite.absolute()),
        conversion_environment_directory=str(
            args.conversion_environment_directory.absolute()
        ),
        conversion_wheelhouse_manifest=str(
            args.conversion_wheelhouse_manifest.absolute()
        ),
        llama_cpp_directory=str(args.llama_cpp_directory.absolute()),
        llama_cpp_revision=args.llama_cpp_revision,
        conversion_model_directory=str(
            args.conversion_model_directory.absolute()
        ),
        canary_suite=str(args.canary_suite.absolute()),
        allowed_licenses=tuple(sorted(set(args.allowed_licenses))),
    )
    store.save(configuration)
    print(json.dumps({
        "configured": True, "configuration": asdict(configuration),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
