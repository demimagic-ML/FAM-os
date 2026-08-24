"""Child-process resource limits for sandbox execution."""

import resource

from fam_os.verification.sandbox import SandboxLimits


def apply_resource_limits(
    limits: SandboxLimits, *, cgroup_memory_managed: bool = False,
) -> None:
    if not cgroup_memory_managed and not limits.unbounded_virtual_address_space:
        resource.setrlimit(resource.RLIMIT_AS, (limits.memory_bytes, limits.memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_bytes, limits.file_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (limits.open_files, limits.open_files))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
