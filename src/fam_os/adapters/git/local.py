"""Shell-free exact-path local Git observation and mutation adapter."""

import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.core.engineering.git_delivery import (
    GitLocalAction,
    GitLocalActionKind,
    GitLocalActionReceipt,
    GitRepositoryObservation,
)
from fam_os.core.engineering.git_publication_proposal import (
    GitPublicationLocalState,
)


_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class LocalGitAdapter:
    def __init__(self, git: Path = Path("/usr/bin/git"), clock=None) -> None:
        if not git.is_absolute() or not git.is_file():
            raise ValueError("Git executable must be an absolute regular file")
        self._git = git
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def observe(self, task_id: str, root: Path) -> GitRepositoryObservation:
        root = self._root(root)
        head = self._optional(root, "rev-parse", "HEAD")
        diff = self._run(root, "diff", "--binary", "--no-ext-diff")
        return GitRepositoryObservation(
            f"git-observation-{uuid4().hex}", task_id, str(root),
            self._run(root, "symbolic-ref", "--short", "HEAD"), head,
            tuple(self._lines(self._run(root, "status", "--porcelain=v1", "-z"), "\0")),
            tuple(self._lines(self._run(root, "for-each-ref", "--format=%(refname)", "refs/heads"))),
            tuple(self._lines(self._run(root, "remote"))),
            tuple(self._lines(self._run(root, "log", "-n", "50", "--format=%H"))) if head else (),
            hashlib.sha256(diff.encode()).hexdigest(), self._clock(),
        )

    def apply(self, action: GitLocalAction) -> GitLocalActionReceipt:
        root = self._root(Path(action.repository_root))
        before = self._optional(root, "rev-parse", "HEAD")
        if action.expected_head_object_id != before:
            raise RuntimeError("Git action baseline head is stale")
        if action.kind is GitLocalActionKind.CREATE_BRANCH:
            if not _REF.fullmatch(action.branch_name or "") or ".." in (action.branch_name or ""):
                raise ValueError("Git branch name is unsafe")
            self._run(root, "switch", "-c", action.branch_name or "")
        elif action.kind is GitLocalActionKind.STAGE_PATHS:
            self._paths(root, action.paths)
            # The exact approved changeset may contain generated artifacts in a
            # repository-ignored directory. Force only these already-validated
            # literal paths; never expand a glob or stage the repository root.
            self._run(root, "add", "-f", "--", *action.paths)
        elif action.kind is GitLocalActionKind.RESTORE_PATHS:
            self._paths(root, action.paths)
            self._run(root, "restore", "--staged", "--worktree", "--", *action.paths)
        elif action.kind is GitLocalActionKind.COMMIT:
            self._run(
                root, "-c", "user.name=FAM OS", "-c",
                "user.email=fam-os@localhost", "commit", "--no-verify",
                "-m", action.message or "",
            )
        after = self._optional(root, "rev-parse", "HEAD")
        status = self._run(root, "status", "--porcelain=v1", "-z")
        staged = tuple(self._lines(self._run(root, "diff", "--cached", "--name-only", "-z"), "\0"))
        return GitLocalActionReceipt(
            f"git-local-receipt-{uuid4().hex}", action.action_id, before,
            after, staged, hashlib.sha256(status.encode()).hexdigest(), self._clock(),
        )

    def staged_paths(self, root: Path | str) -> tuple[str, ...]:
        """Return exact currently staged paths without invoking a shell."""
        root = self._root(Path(root))
        return tuple(self._lines(
            self._run(root, "diff", "--cached", "--name-only", "-z"), "\0",
        ))

    def publication_state(
        self, task_id: str, root: Path | str, remote_name: str,
        expected_before_object_id: str | None,
        expected_after_object_id: str,
    ) -> GitPublicationLocalState:
        """Bind a clean exact local delivery while hashing any remote URL."""
        root = self._root(Path(root))
        observation = self.observe(task_id, root)
        if (
            observation.head_object_id != expected_after_object_id
            or observation.status_porcelain
        ):
            raise RuntimeError("Git publication local state changed after delivery")
        if remote_name not in observation.remote_names:
            raise PermissionError("configured Git publication remote is unavailable")
        source_ref = self._run(root, "symbolic-ref", "HEAD")
        if not source_ref.startswith("refs/heads/") or _protected(source_ref):
            raise PermissionError(
                "Git publication requires a non-protected local feature branch"
            )
        remote_url = self._run_sensitive(
            root, "remote", "get-url", "--push", remote_name,
        )
        if expected_before_object_id is None:
            diff = self._run(
                root, "show", "--binary", "--no-ext-diff", "--format=",
                expected_after_object_id,
            )
        else:
            diff = self._run(
                root, "diff", "--binary", "--no-ext-diff",
                expected_before_object_id, expected_after_object_id, "--",
            )
        return GitPublicationLocalState(
            task_id, str(root), remote_name,
            hashlib.sha256(remote_url.encode()).hexdigest(), source_ref,
            expected_after_object_id, (expected_after_object_id,),
            hashlib.sha256(diff.encode()).hexdigest(), self._clock(),
        )

    def reconcile_commit(
        self, action: GitLocalAction, expected_paths: tuple[str, ...],
    ) -> GitLocalActionReceipt:
        """Recognize only the exact commit that may have completed before persistence."""
        if action.kind is not GitLocalActionKind.COMMIT:
            raise ValueError("Git reconciliation requires a commit action")
        root = self._root(Path(action.repository_root))
        head = self._optional(root, "rev-parse", "HEAD")
        parent = self._optional(root, "rev-parse", "HEAD^")
        message = self._run(root, "show", "-s", "--format=%B", "HEAD")
        paths = tuple(self._lines(self._run(
            root, "diff-tree", "--root", "--no-commit-id", "--name-only",
            "-r", "-z", "HEAD",
        ), "\0"))
        if (
            head is None
            or parent != action.expected_head_object_id
            or message != action.message
            or paths != expected_paths
        ):
            raise RuntimeError("Git head does not match the recorded commit intent")
        status = self._run(root, "status", "--porcelain=v1", "-z")
        return GitLocalActionReceipt(
            f"git-local-receipt-{uuid4().hex}", action.action_id,
            action.expected_head_object_id, head, self.staged_paths(root),
            hashlib.sha256(status.encode()).hexdigest(), self._clock(),
        )

    def reconcile_branch(self, action: GitLocalAction) -> GitLocalActionReceipt:
        """Recognize only the exact feature branch created before persistence."""
        if action.kind is not GitLocalActionKind.CREATE_BRANCH:
            raise ValueError("Git branch reconciliation requires branch creation")
        root = self._root(Path(action.repository_root))
        head = self._optional(root, "rev-parse", "HEAD")
        branch = self._run(root, "symbolic-ref", "--short", "HEAD")
        if head != action.expected_head_object_id or branch != action.branch_name:
            raise RuntimeError("Git head does not match the recorded branch intent")
        status = self._run(root, "status", "--porcelain=v1", "-z")
        return GitLocalActionReceipt(
            f"git-local-receipt-{uuid4().hex}", action.action_id,
            head, head, self.staged_paths(root),
            hashlib.sha256(status.encode()).hexdigest(), self._clock(),
        )

    def blame(self, root: Path, relative_path: str) -> str:
        root = self._root(root)
        self._paths(root, (relative_path,))
        return self._run(root, "blame", "--line-porcelain", "--", relative_path)

    def repository_root(self, selected_directory: Path | str) -> Path:
        """Resolve a repository root from its top-level or any directory inside it."""
        selected = Path(selected_directory).resolve(strict=True)
        if selected.is_symlink() or not selected.is_dir():
            raise ValueError("local Git adapter requires a directory inside a repository")
        try:
            discovered = Path(
                self._run(selected, "rev-parse", "--show-toplevel")
            ).resolve(strict=True)
        except RuntimeError as error:
            raise ValueError(
                "local Git adapter requires a directory inside a repository"
            ) from error
        if discovered.is_symlink() or not discovered.is_dir():
            raise ValueError("Git returned an invalid repository root")
        return discovered

    def _root(self, root: Path) -> Path:
        return self.repository_root(root)

    def _paths(self, root: Path, paths: tuple[str, ...]) -> None:
        for relative in paths:
            if relative == ".gitmodules" or Path(relative).parts[0] == ".git":
                raise PermissionError("Git metadata and submodule policy require distinct authority")
            target = (root / relative).resolve(strict=False)
            if root not in target.parents or target.is_symlink():
                raise PermissionError("Git path escapes repository")
            current = target.parent
            while current != root:
                if (current / ".git").exists():
                    raise PermissionError("Git path enters a nested repository or submodule")
                current = current.parent

    def _optional(self, root, *args):
        try:
            return self._run(root, *args)
        except RuntimeError:
            return None

    def _run(self, root, *args):
        environment = {
            "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
        }
        result = subprocess.run(
            (str(self._git), *args), cwd=root, env=environment,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-4096:])
        return result.stdout.rstrip("\n")

    def _run_sensitive(self, root, *args):
        try:
            return self._run(root, *args)
        except RuntimeError as error:
            raise RuntimeError("sensitive Git observation failed") from error

    @staticmethod
    def _lines(value: str, separator: str = "\n") -> list[str]:
        return [item for item in value.split(separator) if item]


def _protected(ref: str) -> bool:
    return ref in {
        "refs/heads/main", "refs/heads/master", "refs/heads/trunk",
        "refs/heads/production", "refs/heads/prod",
    }
