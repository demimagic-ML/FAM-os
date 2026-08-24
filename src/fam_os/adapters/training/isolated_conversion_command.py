"""Pure command construction for a network-denied llama.cpp conversion."""

from __future__ import annotations

from pathlib import Path

from fam_os.expert_factory import FactoryConversionApproval


def build_isolated_conversion_command(
    *, approval: FactoryConversionApproval, environment: Path,
    worker_script: Path, llama_cpp: Path, model: Path, adapter: Path,
    input_directory: Path, output_directory: Path,
    bubblewrap: str = "/usr/bin/bwrap",
    systemd_run: str = "/usr/bin/systemd-run",
) -> tuple[str, ...]:
    conversion_id = approval.one_use_conversion_id
    paths = (
        environment, worker_script, llama_cpp, model, adapter,
        input_directory, output_directory,
    )
    if any(not path.is_absolute() for path in paths):
        raise ValueError("isolated conversion paths must be absolute")
    if not conversion_id.replace("-", "").isalnum():
        raise ValueError("conversion identity is unsafe for a systemd unit")
    sandbox = (
        bubblewrap, "--unshare-all", "--die-with-parent", "--new-session",
        "--clearenv", "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin", "--ro-bind", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--ro-bind", str(environment), "/environment",
        "--ro-bind", str(worker_script), "/worker/conversion_worker.py",
        "--ro-bind", str(llama_cpp), "/llama.cpp",
        "--ro-bind", str(model), "/model",
        "--ro-bind", str(adapter), "/adapter",
        "--ro-bind", str(input_directory), "/input",
        "--bind", str(output_directory), "/output",
        "--proc", "/proc", "--ro-bind", "/sys", "/sys", "--dev", "/dev",
        "--tmpfs", "/tmp", "--dir", "/home", "--chdir", "/output",
        "--setenv", "PATH", "/environment/bin:/usr/bin:/usr/sbin:/bin",
        "--setenv", "HOME", "/nonexistent",
        "--setenv", "USER", "fam-conversion",
        "--setenv", "LOGNAME", "fam-conversion",
        "--setenv", "XDG_CACHE_HOME", "/tmp/cache",
        "--setenv", "HF_HOME", "/tmp/huggingface",
        "--setenv", "TORCH_HOME", "/tmp/torch",
        "--setenv", "TORCHINDUCTOR_CACHE_DIR", "/tmp/torchinductor",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "HF_HUB_OFFLINE", "1",
        "--setenv", "TRANSFORMERS_OFFLINE", "1",
        "--setenv", "TOKENIZERS_PARALLELISM", "false",
        "--setenv", "PYTHONHASHSEED", "0",
        "/environment/bin/python", "/worker/conversion_worker.py",
        "--config", "/input/config.json",
    )
    return (
        systemd_run, "--user", "--scope", "--quiet", "--collect",
        f"--unit=fam-conversion-{conversion_id}.scope",
        "-p", f"MemoryMax={approval.maximum_ram_bytes}",
        "-p", f"MemoryHigh={int(approval.maximum_ram_bytes * 0.9)}",
        "-p", "MemorySwapMax=0",
        "-p", f"CPUQuota={approval.maximum_cpu_cores * 100}%",
        "-p", "TasksMax=512",
        "-p", f"RuntimeMaxSec={approval.maximum_wall_seconds}",
        "--", *sandbox,
    )
