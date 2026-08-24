"""Pure command construction for one network-denied GPU training worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.expert_factory import FactoryTrainingApproval


@dataclass(frozen=True, slots=True)
class IsolatedTrainingPaths:
    environment: Path
    worker_script: Path
    model: Path
    input_directory: Path
    output_directory: Path

    def __post_init__(self) -> None:
        if any(not item.is_absolute() for item in (
            self.environment, self.worker_script, self.model,
            self.input_directory, self.output_directory,
        )):
            raise ValueError("isolated training paths must be absolute")


def build_isolated_training_command(
    *, job_id: str, approval: FactoryTrainingApproval,
    paths: IsolatedTrainingPaths, bubblewrap: str = "/usr/bin/bwrap",
    systemd_run: str = "/usr/bin/systemd-run",
) -> tuple[str, ...]:
    if not job_id.replace("-", "").isalnum():
        raise ValueError("training job identity is unsafe for a systemd unit")
    sandbox = (
        bubblewrap,
        "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
        "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--ro-bind", str(paths.environment), "/environment",
        "--ro-bind", str(paths.worker_script), "/worker/qlora_worker.py",
        "--ro-bind", str(paths.model), "/model",
        "--ro-bind", str(paths.input_directory), "/input",
        "--bind", str(paths.output_directory), "/output",
        "--proc", "/proc", "--ro-bind", "/sys", "/sys", "--dev", "/dev",
        "--dev-bind-try", "/dev/nvidia0", "/dev/nvidia0",
        "--dev-bind-try", "/dev/nvidiactl", "/dev/nvidiactl",
        "--dev-bind-try", "/dev/nvidia-modeset", "/dev/nvidia-modeset",
        "--dev-bind-try", "/dev/nvidia-uvm", "/dev/nvidia-uvm",
        "--dev-bind-try", "/dev/nvidia-uvm-tools", "/dev/nvidia-uvm-tools",
        "--tmpfs", "/tmp", "--dir", "/home", "--chdir", "/output",
        "--setenv", "PATH", "/environment/bin:/usr/bin:/usr/sbin:/bin",
        "--setenv", "HOME", "/nonexistent",
        "--setenv", "XDG_CACHE_HOME", "/tmp/cache",
        "--setenv", "HF_HOME", "/tmp/huggingface",
        "--setenv", "HF_HUB_CACHE", "/tmp/huggingface/hub",
        "--setenv", "HF_DATASETS_CACHE", "/tmp/huggingface/datasets",
        "--setenv", "TORCH_HOME", "/tmp/torch",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "CUDA_VISIBLE_DEVICES", "0",
        "--setenv", "HF_HUB_OFFLINE", "1",
        "--setenv", "HF_DATASETS_OFFLINE", "1",
        "--setenv", "TRANSFORMERS_OFFLINE", "1",
        "--setenv", "TOKENIZERS_PARALLELISM", "false",
        "--setenv", "PYTHONHASHSEED", str(approval.recipe.seed),
        "/environment/bin/python", "/worker/qlora_worker.py",
        "--config", "/input/config.json",
    )
    return (
        systemd_run, "--user", "--scope", "--quiet", "--collect",
        f"--unit=fam-training-{job_id}.scope",
        "-p", f"MemoryMax={approval.resources.maximum_ram_bytes}",
        "-p", f"MemoryHigh={int(approval.resources.maximum_ram_bytes * 0.9)}",
        "-p", "MemorySwapMax=0",
        "-p", f"CPUQuota={approval.resources.maximum_cpu_cores * 100}%",
        "-p", "TasksMax=512",
        "-p", f"RuntimeMaxSec={approval.maximum_wall_seconds}",
        "--", *sandbox,
    )
