"""Content-bound read-only toolchain mounts for process environments."""

from pathlib import Path
import stat

from fam_os.adapters.bubblewrap.engineering import toolchain_tree_sha256


def recipe_mount_arguments(recipe):
    executable = Path(recipe.executable_path)
    if not recipe.toolchain_mounts:
        _trusted_executable(executable)
        return ()
    arguments = []
    host_executable = None
    directories = sorted({
        str(parent) for mount in recipe.toolchain_mounts
        for parent in Path(mount.sandbox_path).parents
        if str(parent).startswith("/opt")
    }, key=lambda item: (item.count("/"), item))
    for directory in directories:
        arguments.extend(("--dir", directory))
    for mount in recipe.toolchain_mounts:
        source = Path(mount.source_path)
        if source.is_symlink() or not source.exists():
            raise PermissionError("signed process toolchain is missing or symbolic")
        if toolchain_tree_sha256(source) != mount.tree_sha256:
            raise PermissionError("signed process toolchain digest changed")
        arguments.extend(("--ro-bind", mount.source_path, mount.sandbox_path))
        try:
            relative = executable.relative_to(mount.sandbox_path)
        except ValueError:
            continue
        host_executable = source / relative
    if host_executable is None:
        raise PermissionError("signed process executable is outside toolchain mounts")
    _trusted_executable(host_executable)
    return tuple(arguments)


def _trusted_executable(path: Path) -> None:
    resolved = path.resolve(strict=True)
    details = resolved.stat(follow_symlinks=False)
    if (not path.is_absolute() or not stat.S_ISREG(details.st_mode)
            or details.st_uid != 0 or details.st_mode & 0o022):
        raise PermissionError("signed process executable is not immutable and root-owned")
