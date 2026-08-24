"""Network-denied command for one candidate/incumbent evaluator."""

from __future__ import annotations

from pathlib import Path

from fam_os.expert_factory import FactoryEvaluationApproval


def build_isolated_evaluation_command(
    *, approval: FactoryEvaluationApproval, environment: Path,
    worker_script: Path, model: Path, adapter: Path, input_directory: Path,
    output_directory: Path, bubblewrap: str = "/usr/bin/bwrap",
    systemd_run: str = "/usr/bin/systemd-run",
) -> tuple[str, ...]:
    evaluation_id = approval.one_use_evaluation_id
    python_verifier = worker_script.with_name("evaluation_python_verifier.py")
    if not evaluation_id.replace("-", "").isalnum():
        raise ValueError("evaluation identity is unsafe for a systemd unit")
    sandbox = (
        bubblewrap, "--unshare-all", "--die-with-parent", "--new-session",
        "--clearenv", "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin", "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--ro-bind", str(environment), "/environment",
        "--ro-bind", str(worker_script), "/worker/evaluator.py",
        "--ro-bind", str(python_verifier), "/worker/python-verifier.py",
        "--ro-bind", str(model), "/model",
        "--ro-bind", str(adapter), "/adapter",
        "--ro-bind", str(input_directory), "/input",
        "--bind", str(output_directory), "/output",
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
        "--setenv", "HF_HUB_OFFLINE", "1",
        "--setenv", "HF_DATASETS_OFFLINE", "1",
        "--setenv", "TRANSFORMERS_OFFLINE", "1",
        "--setenv", "TOKENIZERS_PARALLELISM", "false",
        "--setenv", "CUDA_VISIBLE_DEVICES", "0",
        "/environment/bin/python", "/worker/evaluator.py",
        "--config", "/input/config.json",
    )
    return (
        systemd_run, "--user", "--scope", "--quiet", "--collect",
        f"--unit=fam-evaluation-{evaluation_id}.scope",
        "-p", f"MemoryMax={approval.policy.maximum_peak_ram_bytes}",
        "-p", f"MemoryHigh={int(approval.policy.maximum_peak_ram_bytes * 0.9)}",
        "-p", "MemorySwapMax=0", "-p", "CPUQuota=1200%",
        "-p", "TasksMax=512", "-p", "RuntimeMaxSec=900", "--", *sandbox,
    )
