"""General shell-free engineering recipe execution in candidate sandboxes."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.bubblewrap.process import ProcessLauncher, SubprocessProcessLauncher
from fam_os.adapters.bubblewrap.settings import BubblewrapSettings
from fam_os.core.engineering.execution import (
    EngineeringSandboxProfile, EngineeringToolReceipt, SandboxNetworkMode,
    SignedToolRecipe, ToolQualificationStatus, ToolchainMountSourceKind,
)
from fam_os.core.engineering.diagnostic_redaction import (
    sanitize_diagnostic_evidence,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.transactions import CandidateWorkspace
from fam_os.verification.sandbox import IsolationLevel, SandboxLimits, SandboxStatus


class EngineeringSandboxAdapter:
    def __init__(
        self,
        recipe_catalog: SignedToolRecipeCatalog,
        bubblewrap: Path = Path("/usr/bin/bwrap"),
        systemd_run: Path = Path("/usr/bin/systemd-run"),
        aa_exec: Path = Path("/usr/bin/aa-exec"),
        launcher: ProcessLauncher | None = None,
        clock=None,
        release_root: Path | None = None,
        apparmor_profile: str | None = None,
    ) -> None:
        for path in (bubblewrap, systemd_run):
            if not path.is_absolute() or not path.is_file():
                raise ValueError("engineering sandbox executables must exist and be absolute")
        self._catalog = recipe_catalog
        self._bubblewrap = bubblewrap
        self._systemd_run = systemd_run
        self._launcher = launcher or SubprocessProcessLauncher()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Reuse the shared adapter validation so a profile name can never be
        # interpreted as another systemd-run option.
        BubblewrapSettings(apparmor_profile=apparmor_profile)
        self._apparmor_profile = apparmor_profile
        if apparmor_profile is not None and (
            not aa_exec.is_absolute() or not aa_exec.is_file()
        ):
            raise ValueError("engineering AppArmor transition executable is unavailable")
        self._aa_exec = aa_exec
        self._release_root = (
            None if release_root is None else release_root.resolve(strict=True)
        )

    def run(
        self,
        task_id: str,
        candidate: CandidateWorkspace,
        recipe_id: str,
        recipe_version: str,
        profile: EngineeringSandboxProfile,
    ) -> EngineeringToolReceipt:
        recipe = self._catalog.get(recipe_id, recipe_version)
        started = self._clock()
        root = Path(candidate.candidate_workspace)
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise PermissionError("engineering candidate root is invalid")
        if profile.network_mode is not SandboxNetworkMode.DENIED:
            raise PermissionError("networked recipes require the allowlist proxy adapter")
        if recipe.network_mode is not profile.network_mode:
            raise PermissionError("recipe and sandbox network modes differ")
        command = self.build_command(root, recipe, profile)
        limits = SandboxLimits(
            wall_seconds=float(profile.wall_seconds),
            memory_bytes=profile.memory_bytes,
            cpu_seconds=profile.cpu_seconds,
            file_bytes=profile.artifact_bytes,
            open_files=64,
            processes=profile.process_limit,
            output_bytes=profile.output_bytes,
        )
        result = self._launcher.run(
            command, limits, profile.sanitized_environment,
            IsolationLevel.BUBBLEWRAP,
        )
        namespace_retry = _namespace_setup_failed(result)
        if namespace_retry:
            # A namespace setup failure occurs before the signed tool starts,
            # so one bounded retry cannot duplicate candidate effects.
            result = self._launcher.run(
                command, limits, profile.sanitized_environment,
                IsolationLevel.BUBBLEWRAP,
            )
        completed = self._clock()
        status = ToolQualificationStatus.UNAVAILABLE
        namespace_setup_failed = _namespace_setup_failed(result)
        if result.status is SandboxStatus.COMPLETED and not namespace_setup_failed:
            status = (
                ToolQualificationStatus.PASSED
                if result.exit_code in recipe.expected_exit_codes
                else ToolQualificationStatus.FAILED
            )
        diagnostic = (
            "Bubblewrap could not establish the required namespaces"
            if namespace_setup_failed
            else (result.stdout + result.stderr + result.reason)[-4_096:]
        )
        if namespace_retry and not namespace_setup_failed:
            diagnostic = ("namespace setup recovered after one bounded retry\n" + diagnostic)[-4_096:]
        return EngineeringToolReceipt(
            f"tool-receipt-{uuid4().hex}", task_id, candidate.candidate_id,
            recipe.recipe_id, recipe.payload_sha256, profile.profile_id,
            _digest_bytes("\0".join(command).encode()), started, completed,
            result.exit_code, _digest_text(result.stdout), _digest_text(result.stderr),
            (), (), ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"),
            status, sanitize_diagnostic_evidence(diagnostic),
        )

    def build_command(
        self,
        candidate_root: Path,
        recipe: SignedToolRecipe,
        profile: EngineeringSandboxProfile,
        argv: tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        environment = dict(profile.sanitized_environment)
        environment.update({
            "HOME": "/tmp/fam-home",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TEMPLATE_DIR": "/nonexistent",
        })
        inner = [
            str(self._bubblewrap), "--unshare-all", "--die-with-parent",
            "--new-session", "--clearenv", "--cap-drop", "ALL",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind-try", "/lib64", "/lib64", "--proc", "/proc",
            "--ro-bind-try", "/etc/java-21-openjdk", "/etc/java-21-openjdk",
            "--dev", "/dev", "--bind", str(candidate_root), "/workspace",
            "--tmpfs", "/tmp", "--tmpfs", "/home", "--chdir", "/workspace",
        ]
        mount_directories = sorted({
            str(parent)
            for mount in recipe.toolchain_mounts
            for parent in Path(mount.sandbox_path).parents
            if str(parent).startswith("/opt")
        }, key=lambda value: (value.count("/"), value))
        for directory in mount_directories:
            inner.extend(("--dir", directory))
        for mount in recipe.toolchain_mounts:
            source = self._mount_source(mount)
            if not source.exists() or source.is_symlink():
                raise PermissionError("signed toolchain mount is missing or symbolic")
            if toolchain_tree_sha256(source) != mount.tree_sha256:
                raise PermissionError("signed toolchain mount digest changed")
            inner.extend(("--ro-bind", str(source), mount.sandbox_path))
        for key, value in sorted(environment.items()):
            inner.extend(("--setenv", key, value))
        inner.append("--")
        inner.append(recipe.executable_path)
        arguments = recipe.argv_template if argv is None else argv
        inner.extend(value.replace("{workspace}", "/workspace") for value in arguments)
        cpu_quota = max(1, int(100 * profile.cpu_seconds / profile.wall_seconds))
        properties = (
            "-p", f"TasksMax={profile.process_limit}",
            "-p", f"MemoryMax={profile.memory_bytes}",
            "-p", "MemorySwapMax=0", "-p", f"CPUQuota={cpu_quota}%",
        )
        if self._apparmor_profile is None:
            return (
                str(self._systemd_run), "--user", "--scope", "--collect", "--quiet",
                *properties, "--", *inner,
            )
        return (
            str(self._systemd_run), "--user", "--scope", "--collect", "--quiet",
            *properties, "--", str(self._aa_exec), "-p",
            self._apparmor_profile, "--", *inner,
        )

    def _mount_source(self, mount) -> Path:
        if mount.source_kind is ToolchainMountSourceKind.HOST_ABSOLUTE:
            return Path(mount.source_path)
        if self._release_root is None:
            raise PermissionError("installed release toolchain root is unavailable")
        source = self._release_root.joinpath(mount.source_path).resolve(strict=True)
        if not source.is_relative_to(self._release_root):
            raise PermissionError("installed release toolchain escapes its release")
        return source


def _digest_text(value: str) -> str:
    return _digest_bytes(value.encode("utf-8"))


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _namespace_setup_failed(result) -> bool:
    return (
        result.status is SandboxStatus.COMPLETED
        and result.exit_code != 0
        and result.stderr.lstrip().startswith("bwrap:")
    )


def toolchain_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    paths = (root,) if root.is_file() else tuple(sorted(root.rglob("*")))
    for path in paths:
        if path.is_symlink():
            raise PermissionError("toolchain mount tree contains a symbolic link")
        relative = "." if path == root else path.relative_to(root).as_posix()
        if path.is_dir():
            digest.update(f"directory:{relative}\n".encode())
        elif path.is_file():
            digest.update(f"file:{relative}:".encode())
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65_536), b""):
                    digest.update(chunk)
            digest.update(b"\n")
        else:
            raise PermissionError("toolchain mount tree contains an unsupported entry")
    return digest.hexdigest()
