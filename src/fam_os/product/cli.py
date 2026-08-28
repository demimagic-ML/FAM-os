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
from fam_os.product.omarchy_setup import OmarchySetup
from fam_os.adapters.omarchy.diagnostics import diagnose_omarchy
from fam_os.product.omarchy_session_bridge import run_omarchy_session_bridge
from fam_os.product.agent_usage import print_omarchy_usage
from fam_os.product.desktop_permissions import DesktopPermissionStore
from fam_os.product.omarchy_agent_client import (
    default_runtime_root, submit_from_omarchy,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fam-os")
    parser.add_argument("--prefix", type=Path, default=_installation_prefix())
    parser.add_argument(
        "--trusted-key", action="append", default=[], metavar="KEY_ID=PUBLIC_KEY_PEM",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        command = commands.add_parser(name)
        command.add_argument("--bundle", type=Path, required=True)
    diagnose = commands.add_parser("diagnose")
    diagnose.add_argument("target", nargs="?", choices=("omarchy",))
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--omarchy", action="store_true", required=True)
    doctor.add_argument("--json", action="store_true")
    setup = commands.add_parser("setup")
    setup.add_argument("target", choices=("omarchy",))
    setup.add_argument("--enable-widget", action=argparse.BooleanOptionalAction, default=True)
    setup.add_argument("--no-start", action="store_true")
    setup.add_argument("--yes", action="store_true")
    setup.add_argument("--allow-experimental", action="store_true")
    session = commands.add_parser("session")
    session.add_argument("target", choices=("omarchy",))
    usage = commands.add_parser("usage")
    usage.add_argument("--state-root", type=Path, default=_state_root())
    usage.add_argument("--omarchy", action="store_true", required=True)
    usage.add_argument("--output", type=Path)
    agent = commands.add_parser("agent")
    agent.add_argument("prompt", nargs="*")
    agent.add_argument("--goal", action="store_true")
    agent.add_argument("--authority", choices=("workspace", "application_test", "full_os"), default="workspace")
    agent.add_argument("--workspace", type=Path, default=Path.cwd())
    agent.add_argument("--runtime-root", type=Path, default=default_runtime_root())
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--release-id", required=True)
    commands.add_parser("enable")
    commands.add_parser("disable")
    repair = commands.add_parser("repair")
    repair.add_argument("target", nargs="?", choices=("omarchy",))
    repair.add_argument("--widget", action="store_true")
    repair.add_argument("--service", action="store_true")
    repair.add_argument("--yes", action="store_true")
    purge = commands.add_parser("purge")
    purge.add_argument("--user-data", action="store_true", required=True)
    purge.add_argument("--yes", action="store_true")
    permissions = commands.add_parser("permissions")
    permissions.add_argument("target", choices=("desktop",))
    permissions.add_argument("--state-root", type=Path, default=_state_root())
    permissions.add_argument(
        "--screen-capture", choices=("on", "off"),
        help="globally enable or disable configured exact-window capture targets",
    )
    permissions.add_argument(
        "--input-control", choices=("on", "off"),
        help="globally enable or disable configured exact-window input targets",
    )
    remove = commands.add_parser("remove")
    remove.add_argument("--state-root", type=Path, default=_state_root())
    remove.add_argument("--runtime-root", type=Path, default=_runtime_root())
    remove.add_argument(
        "--extension-root", type=Path,
        default=Path.home() / ".vscode/extensions",
    )
    remove.add_argument("--confirm", action="store_true")
    remove.add_argument("target", nargs="?", choices=("omarchy-integration",))
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
    if args.command == "usage":
        return print_omarchy_usage(
            args.state_root.absolute(),
            None if args.output is None else args.output.absolute(),
        )
    if args.command == "agent":
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            prompt = input("What should FAM do? ").strip()
        if not prompt:
            raise ValueError("agent prompt must not be empty")
        result = submit_from_omarchy(
            prompt, args.workspace, goal_mode=args.goal,
            authority_profile=args.authority,
            runtime_root=args.runtime_root.absolute(),
        )
        print(json.dumps(result, default=str, sort_keys=True))
        return 0
    if args.command == "session":
        return run_omarchy_session_bridge()
    if args.command == "setup":
        if args.enable_widget:
            _confirm_unsandboxed_plugin(args.yes)
        receipt = OmarchySetup().setup(
            enable_widget=args.enable_widget, start=not args.no_start,
            allow_experimental=args.allow_experimental,
        )
        print(json.dumps(asdict(receipt), default=str, sort_keys=True))
        return 0 if receipt.configured else 1
    if args.command == "doctor" or (
        args.command == "diagnose" and args.target == "omarchy"
    ):
        receipt = diagnose_omarchy()
        if args.command == "doctor" and not args.json:
            for check in receipt.checks:
                print(f"{check.status.value.upper():8} {check.detail}")
                if check.status.value != "pass" and check.fix:
                    print(f"FIX      {check.fix}")
        else:
            print(json.dumps(receipt.document(), default=str, sort_keys=True))
        return 0 if receipt.healthy else 1
    if args.command == "repair" and args.target == "omarchy":
        if args.widget:
            _confirm_unsandboxed_plugin(args.yes)
        receipt = OmarchySetup().repair(widget=args.widget, service=args.service)
        print(json.dumps(asdict(receipt), default=str, sort_keys=True))
        return 0 if receipt.configured else 1
    if args.command == "remove" and args.target == "omarchy-integration":
        receipt = OmarchySetup().remove()
        print(json.dumps(asdict(receipt), default=str, sort_keys=True))
        return 0
    if args.command == "purge":
        receipt = OmarchySetup().purge_user_data(
            confirmed=args.user_data and args.yes,
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0
    if args.command == "permissions":
        store = DesktopPermissionStore(
            args.state_root.absolute() / "config/fallbacks.json",
        )
        if args.screen_capture is None and args.input_control is None:
            receipt = store.status()
        else:
            receipt = store.update(
                screen_capture=_on_off(args.screen_capture),
                input_control=_on_off(args.input_control),
            )
        print(json.dumps(receipt, sort_keys=True))
        return 0
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
        if not _system_package_installed():
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


def _installation_prefix() -> Path:
    return Path(os.environ.get(
        "FAM_OS_PREFIX", Path.home() / ".local/share/fam-os-installation",
    ))


def _system_package_installed() -> bool:
    marker = Path("/usr/share/fam-os/arch-package.json")
    configured = os.environ.get("FAM_OS_SYSTEM_PACKAGE_MARKER")
    return marker.is_file() or bool(configured and Path(configured).is_file())


def _confirm_unsandboxed_plugin(assume_yes: bool) -> None:
    if assume_yes:
        return
    if not os.isatty(0):
        raise PermissionError(
            "Omarchy plugins run unsandboxed inside the desktop shell; "
            "rerun with --yes after reviewing the plugin source",
        )
    response = input(
        "Install the Git-backed FAM plugin inside Omarchy's unsandboxed shell? "
        "[y/N] ",
    ).strip().casefold()
    if response not in {"y", "yes"}:
        raise PermissionError("Omarchy plugin installation was not confirmed")


def _on_off(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "on"


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
