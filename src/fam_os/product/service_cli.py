"""Command-line entry point for the composed local product service."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
from pathlib import Path

from fam_os.adapters.codex_subscription import CodexSubscriptionSettings
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.product.composition.factory_training import FactoryTrainingRuntimeSettings
from fam_os.product.composition.factory_evaluation import FactoryEvaluationRuntimeSettings
from fam_os.product.composition.factory_release import FactoryReleaseRuntimeSettings
from fam_os.product.peer_configuration import PeerConfigurationStore
from fam_os.product.host_security import required_sandbox_apparmor_profile
from fam_os.product.factory_runtime_configuration import (
    FactoryRuntimeConfiguration,
    FactoryRuntimeConfigurationStore,
)
from fam_os.product.composition.validation_profiles import (
    SUPPORTED_VALIDATION_PROFILE_IDS,
    load_validation_profile,
    validation_profile_resource_limits,
)
from fam_os.supervisor import ResourceLimits


class _ServiceTerminationRequested(BaseException):
    """Interrupt startup or waiting without resuming after a process signal."""


def _request_service_termination(*_args) -> None:
    raise _ServiceTerminationRequested


def run(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FAM_OS local product service")
    parser.add_argument("--state-root", type=Path, default=_state_root())
    parser.add_argument("--runtime-root", type=Path, default=_runtime_root())
    parser.add_argument("--model", default="qwen3:1.7b")
    parser.add_argument(
        "--engineering-model", default=None,
        help=(
            "preferred local model for agentic engineering; when omitted FAM uses "
            "the strongest recognized installed coding model and falls back to --model"
        ),
    )
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11435")
    parser.add_argument("--external-ollama", action="store_true")
    parser.add_argument(
        "--engineering-provider",
        choices=("ollama", "codex-subscription"), default="ollama",
        help="provider used only for bounded engineering candidate generation",
    )
    parser.add_argument("--codex-executable", type=Path, default=Path("codex"))
    parser.add_argument("--codex-model", default="gpt-5.6-sol")
    parser.add_argument(
        "--codex-reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        default="medium",
    )
    parser.add_argument("--codex-timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--sandbox-apparmor-profile",
        default=required_sandbox_apparmor_profile(),
    )
    parser.add_argument(
        "--validation-profile", choices=SUPPORTED_VALIDATION_PROFILE_IDS,
    )
    parser.add_argument("--ollama-executable", type=Path, default=Path("/usr/local/bin/ollama"))
    parser.add_argument("--source-model-root", type=Path, default=_source_model_root())
    parser.add_argument("--console-port", type=int, default=8765)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--device-name")
    parser.add_argument("--peer-listen-host")
    parser.add_argument("--peer-listen-port", type=int)
    parser.add_argument(
        "--integration-network-broker-socket", type=Path,
        default=_integration_network_broker_socket(),
        help="opt in to privileged integration egress through this Unix socket",
    )
    parser.add_argument(
        "--git-publication-broker-socket", type=Path,
        default=_git_publication_broker_socket(),
        help="opt in to credential-opaque Git publication through this Unix socket",
    )
    parser.add_argument(
        "--git-publication-remote", default=_git_publication_remote(),
        help="allow natural publication only through this configured Git remote name",
    )
    parser.add_argument(
        "--git-publication-credential-ref",
        default=_git_publication_credential_ref(),
        help="opaque broker credential reference for the configured Git remote",
    )
    parser.add_argument("--training-environment-directory", type=Path)
    parser.add_argument("--training-wheelhouse-manifest", type=Path)
    parser.add_argument("--training-model-directory", type=Path)
    parser.add_argument("--evaluation-suite", type=Path)
    parser.add_argument("--conversion-environment-directory", type=Path)
    parser.add_argument("--conversion-wheelhouse-manifest", type=Path)
    parser.add_argument("--llama-cpp-directory", type=Path)
    parser.add_argument("--llama-cpp-revision")
    parser.add_argument("--conversion-model-directory", type=Path)
    parser.add_argument("--factory-canary-suite", type=Path)
    parser.add_argument(
        "--factory-allowed-license", action="append", dest="factory_licenses",
    )
    args = parser.parse_args(argv)
    state_root = args.state_root.absolute()
    validation_profile = (
        None
        if args.validation_profile is None
        else load_validation_profile(args.validation_profile)
    )
    if (
        validation_profile is not None
        and args.external_ollama
        and validation_profile.service.accelerator_visibility.value == "deny_all"
    ):
        parser.error(
            "compat-cpu-16gb requires managed Ollama so accelerator denial and "
            "the service cgroup can be enforced"
        )
    factory_configuration = _installed_factory_configuration(
        args, state_root,
    )
    codex_subscription = _codex_subscription_settings(args, parser)
    peer = PeerConfigurationStore(
        state_root / "config/peer.json", os.geteuid(),
    ).load()
    service = LocalProductService(ProductServiceSettings(
        state_root=state_root,
        runtime_root=args.runtime_root.absolute(),
        model_ref=args.model,
        engineering_model_ref=args.engineering_model,
        ollama_url=args.ollama_url,
        console_port=args.console_port,
        ready_file=args.ready_file,
        manage_ollama=not args.external_ollama,
        ollama_executable=args.ollama_executable,
        source_model_root=args.source_model_root,
        resource_limits=(
            _default_model_limits()
            if validation_profile is None
            else validation_profile_resource_limits(validation_profile)
        ),
        device_display_name=args.device_name or peer.display_name,
        peer_listen_host=(
            args.peer_listen_host if args.peer_listen_host is not None
            else peer.listen_host if peer.enabled else None
        ),
        peer_listen_port=args.peer_listen_port or peer.listen_port,
        factory_training_runtime=_factory_training_settings(
            args, state_root, parser, factory_configuration,
        ),
        factory_evaluation_runtime=_factory_evaluation_settings(
            args, state_root, parser, factory_configuration,
        ),
        factory_release_runtime=_factory_release_settings(
            args, state_root, parser, factory_configuration,
        ),
        validation_profile=validation_profile,
        sandbox_apparmor_profile=args.sandbox_apparmor_profile,
        integration_network_broker_socket=(
            args.integration_network_broker_socket
        ),
        git_publication_broker_socket=args.git_publication_broker_socket,
        git_publication_remote_name=args.git_publication_remote,
        git_publication_credential_ref=args.git_publication_credential_ref,
        codex_subscription=codex_subscription,
    ))
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, _request_service_termination)
    try:
        service.start()
        service.wait()
    except _ServiceTerminationRequested:
        pass
    finally:
        service.stop()
    return 0


def _state_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "fam-os"


def _codex_subscription_settings(args, parser):
    if args.engineering_provider != "codex-subscription":
        return None
    executable = args.codex_executable
    if not executable.is_absolute():
        discovered = shutil.which(str(executable))
        if discovered is None:
            parser.error("codex-subscription requires an installed Codex CLI")
        executable = Path(discovered)
    executable = executable.absolute()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        parser.error("configured Codex CLI is not executable")
    return CodexSubscriptionSettings(
        executable=executable,
        work_root=args.runtime_root.absolute() / "codex-inference",
        home=Path.home().absolute(),
        model_ref=args.codex_model,
        reasoning_effort=args.codex_reasoning_effort,
        timeout_seconds=args.codex_timeout_seconds,
    )


def _runtime_root() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}")) / "fam-os"


def _source_model_root() -> Path | None:
    candidates = (
        Path("/usr/share/ollama/.ollama/models"),
        Path.home() / ".ollama/models",
    )
    return next((path for path in candidates if path.is_dir()), None)


def _integration_network_broker_socket() -> Path | None:
    value = os.environ.get("FAM_INTEGRATION_NETWORK_BROKER_SOCKET")
    return None if value is None else Path(value)


def _git_publication_broker_socket() -> Path | None:
    value = os.environ.get("FAM_GIT_PUBLICATION_BROKER_SOCKET")
    return None if value is None else Path(value)


def _git_publication_remote() -> str | None:
    return os.environ.get("FAM_GIT_PUBLICATION_REMOTE")


def _git_publication_credential_ref() -> str | None:
    return os.environ.get("FAM_GIT_PUBLICATION_CREDENTIAL_REF")


def _default_model_limits() -> ResourceLimits:
    total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    reserve = 12 * 1024**3 if total > 32 * 1024**3 else 2 * 1024**3
    maximum = max(2 * 1024**3, total - reserve)
    cpus = max(1, (os.cpu_count() or 1) - (2 if (os.cpu_count() or 1) > 4 else 1))
    return ResourceLimits(
        memory_max_bytes=maximum,
        swap_max_bytes=0,
        cpu_quota_percent=cpus * 100,
        tasks_max=512,
        memory_high_bytes=int(maximum * .9),
    )


def _factory_training_settings(
    args, state_root: Path, parser: argparse.ArgumentParser,
    configuration: FactoryRuntimeConfiguration | None = None,
) -> FactoryTrainingRuntimeSettings | None:
    if configuration is not None:
        from fam_os.adapters.training import qlora_worker

        return FactoryTrainingRuntimeSettings(
            Path(configuration.training_environment_directory),
            Path(configuration.training_wheelhouse_manifest),
            Path(configuration.training_model_directory),
            Path(qlora_worker.__file__).absolute(),
            (state_root / "factory/training/jobs").absolute(),
        )
    paths = (
        args.training_environment_directory,
        args.training_wheelhouse_manifest,
        args.training_model_directory,
    )
    if not any(paths):
        return None
    if not all(paths):
        parser.error(
            "real training requires environment, wheelhouse manifest, and model paths",
        )
    from fam_os.adapters.training import qlora_worker

    return FactoryTrainingRuntimeSettings(
        args.training_environment_directory.absolute(),
        args.training_wheelhouse_manifest.absolute(),
        args.training_model_directory.absolute(),
        Path(qlora_worker.__file__).absolute(),
        (state_root / "factory/training/jobs").absolute(),
    )


def _factory_evaluation_settings(
    args, state_root: Path, parser: argparse.ArgumentParser,
    configuration: FactoryRuntimeConfiguration | None = None,
) -> FactoryEvaluationRuntimeSettings | None:
    if configuration is not None:
        from fam_os.adapters.training import evaluation_worker

        return FactoryEvaluationRuntimeSettings(
            Path(configuration.training_environment_directory),
            Path(configuration.training_wheelhouse_manifest),
            Path(configuration.training_model_directory),
            Path(evaluation_worker.__file__).absolute(),
            (state_root / "factory/evaluation/runs").absolute(),
            (state_root / "factory/training/jobs").absolute(),
            Path(configuration.evaluation_suite),
        )
    training = (
        args.training_environment_directory,
        args.training_wheelhouse_manifest,
        args.training_model_directory,
    )
    if args.evaluation_suite is None:
        return None
    if not all(training):
        parser.error("real evaluation requires all real training runtime paths")
    from fam_os.adapters.training import evaluation_worker

    return FactoryEvaluationRuntimeSettings(
        args.training_environment_directory.absolute(),
        args.training_wheelhouse_manifest.absolute(),
        args.training_model_directory.absolute(),
        Path(evaluation_worker.__file__).absolute(),
        (state_root / "factory/evaluation/runs").absolute(),
        (state_root / "factory/training/jobs").absolute(),
        args.evaluation_suite.absolute(),
    )


def _factory_release_settings(
    args, state_root: Path, parser: argparse.ArgumentParser,
    configuration: FactoryRuntimeConfiguration | None = None,
) -> FactoryReleaseRuntimeSettings | None:
    if configuration is not None:
        return _release_settings_from_configuration(
            configuration, args, state_root,
        )
    required = (
        args.conversion_environment_directory,
        args.conversion_wheelhouse_manifest,
        args.llama_cpp_directory,
        args.llama_cpp_revision,
        args.conversion_model_directory,
        args.factory_canary_suite,
    )
    if not any(required):
        return None
    if not all(required):
        parser.error(
            "real specialist release requires conversion environment, wheelhouse "
            "manifest, llama.cpp directory and revision, model directory, and "
            "canary suite",
        )
    return FactoryReleaseRuntimeSettings(
        conversion_environment=args.conversion_environment_directory.absolute(),
        conversion_wheelhouse_manifest=(
            args.conversion_wheelhouse_manifest.absolute()
        ),
        llama_cpp_directory=args.llama_cpp_directory.absolute(),
        llama_cpp_revision=args.llama_cpp_revision,
        model_directory=args.conversion_model_directory.absolute(),
        training_workspace_root=(state_root / "factory/training/jobs").absolute(),
        conversion_workspace_root=(
            state_root / "factory/conversion/jobs"
        ).absolute(),
        package_output_root=(state_root / "factory/packages/output").absolute(),
        package_artifact_root=(
            state_root / "factory/packages/artifacts"
        ).absolute(),
        package_lifecycle_state=(
            state_root / "factory/packages/lifecycle.json"
        ).absolute(),
        canary_workspace_root=(state_root / "factory/canary/runs").absolute(),
        canary_suite=args.factory_canary_suite.absolute(),
        ollama_executable=args.ollama_executable.absolute(),
        ollama_url=args.ollama_url,
        allowed_licenses=tuple(args.factory_licenses or ("Apache-2.0",)),
    )


def _installed_factory_configuration(
    args, state_root: Path,
) -> FactoryRuntimeConfiguration | None:
    explicit = (
        args.training_environment_directory,
        args.training_wheelhouse_manifest,
        args.training_model_directory,
        args.evaluation_suite,
        args.conversion_environment_directory,
        args.conversion_wheelhouse_manifest,
        args.llama_cpp_directory,
        args.llama_cpp_revision,
        args.conversion_model_directory,
        args.factory_canary_suite,
        args.factory_licenses,
    )
    if any(explicit):
        return None
    return FactoryRuntimeConfigurationStore(
        state_root / "config/factory-runtime.json", os.geteuid(),
    ).load()


def _release_settings_from_configuration(
    configuration: FactoryRuntimeConfiguration, args, state_root: Path,
) -> FactoryReleaseRuntimeSettings:
    return FactoryReleaseRuntimeSettings(
        conversion_environment=Path(
            configuration.conversion_environment_directory,
        ),
        conversion_wheelhouse_manifest=Path(
            configuration.conversion_wheelhouse_manifest,
        ),
        llama_cpp_directory=Path(configuration.llama_cpp_directory),
        llama_cpp_revision=configuration.llama_cpp_revision,
        model_directory=Path(configuration.conversion_model_directory),
        training_workspace_root=(state_root / "factory/training/jobs").absolute(),
        conversion_workspace_root=(
            state_root / "factory/conversion/jobs"
        ).absolute(),
        package_output_root=(state_root / "factory/packages/output").absolute(),
        package_artifact_root=(
            state_root / "factory/packages/artifacts"
        ).absolute(),
        package_lifecycle_state=(
            state_root / "factory/packages/lifecycle.json"
        ).absolute(),
        canary_workspace_root=(state_root / "factory/canary/runs").absolute(),
        canary_suite=Path(configuration.canary_suite),
        ollama_executable=args.ollama_executable.absolute(),
        ollama_url=args.ollama_url,
        allowed_licenses=configuration.allowed_licenses,
    )
