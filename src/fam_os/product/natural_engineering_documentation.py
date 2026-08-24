"""Natural-loop coordinator for signed deterministic generated content."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fam_os.core.engineering import (
    CandidateArtifact, CandidateContentKind, CandidateEditStatus,
    CandidateOperation, CandidateOperationKind,
    DOCUMENTATION_OUTPUT_PATHS, DOCUMENTATION_OWNERSHIP_PATH,
    DOCUMENTATION_REGENERATION_PATH, DOCUMENTATION_REQUIREMENTS_PATH,
    DocumentationGenerationRequest,
    DocumentationGenerationService, DocumentationRequirementPolicy,
    DocumentationRequirementSelection, DocumentationSource,
    DocumentationSourceContent,
    GeneratedDocumentationReceipt,
)


class NaturalEngineeringDocumentationCoordinator:
    def __init__(
        self, loop, generation: DocumentationGenerationService,
        policy: DocumentationRequirementPolicy | None = None, *, clock=None,
    ) -> None:
        self._loop = loop
        self._generation = generation
        self._policy = policy or DocumentationRequirementPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(
        self, owner_id: str, definition, *, session_id: str,
        principal_id: str, preferred_paths: tuple[str, ...],
    ) -> tuple[GeneratedDocumentationReceipt, ...]:
        kinds = self._policy.required_kinds(definition.task.intent)
        preparation = self._loop.preparation(owner_id, definition.task.task_id)
        intent_digest = hashlib.sha256(definition.task.intent.encode()).hexdigest()
        selection = DocumentationRequirementSelection(
            _identity(
                "documentation-selection", definition.task.task_id,
                preparation.candidate.candidate_id, self._policy.policy_id,
                intent_digest, *(item.value for item in kinds),
            ),
            definition.task.task_id, preparation.candidate.candidate_id,
            self._policy.policy_id, intent_digest, kinds, definition.created_at,
        )
        self._loop.record_documentation_selection(owner_id, selection)
        if not kinds:
            return ()
        root = Path(preparation.candidate.candidate_workspace)
        existing = self._loop.documentation_for_task(
            owner_id, definition.task.task_id,
        )
        receipts = {
            item.request_id: item for item in existing
            if isinstance(item, GeneratedDocumentationReceipt)
        }
        recipes = tuple(self._generation.select(kind) for kind in kinds)
        governance = _governance_content(definition, recipes)
        plans = tuple(
            (*self._request(
                definition, preparation.candidate.candidate_id, root,
                recipe, preferred_paths, governance,
            ), recipe)
            for recipe in recipes
        )
        for request, _sources, _recipe in plans:
            if request.request_id not in receipts:
                self._loop.begin_documentation_generation(owner_id, request)
        self._write_governance_files(
            owner_id, definition, governance,
            session_id=session_id, principal_id=principal_id,
        )
        values = []
        for request, sources, recipe in plans:
            prior = receipts.get(request.request_id)
            if prior is not None:
                values.append(prior)
                continue
            selected, content = self._generation.generate(request, sources)
            self._write_file(
                owner_id, definition.task.task_id, request.output_path,
                content, selected.output_media_type, selected.coordinate,
                session_id=session_id, principal_id=principal_id,
            )
            receipt = GeneratedDocumentationReceipt(
                _identity("documentation-receipt", request.request_id),
                request.request_id, request.task_id, request.candidate_id,
                request.output_path, hashlib.sha256(content).hexdigest(),
                selected.coordinate, request.sources, self._clock(), True,
            )
            self._loop.record_generated_documentation(
                owner_id, request, receipt,
            )
            values.append(receipt)
        return tuple(values)

    def _request(
        self, definition, candidate_id, root, recipe, preferred_paths,
        governance,
    ):
        sources = _source_content(
            root, preferred_paths, recipe.maximum_source_files,
            recipe.maximum_source_bytes,
        )
        output_path = DOCUMENTATION_OUTPUT_PATHS[recipe.kind]
        request_id = _identity(
            "documentation-request", definition.task.task_id, candidate_id,
            recipe.coordinate, output_path,
            *(item.source.content_sha256 for item in sources),
            *(hashlib.sha256(content).hexdigest() for _path, content in governance),
        )
        request = DocumentationGenerationRequest(
            request_id, definition.task.task_id, candidate_id, recipe.kind,
            output_path, recipe.coordinate, DOCUMENTATION_OWNERSHIP_PATH,
            DOCUMENTATION_REGENERATION_PATH,
            tuple(item.source for item in sources), definition.created_at,
        )
        return request, sources

    def _write_governance_files(
        self, owner_id, definition, governance, *, session_id, principal_id,
    ) -> None:
        for path, content in governance:
            self._write_file(
                owner_id, definition.task.task_id, path, content,
                "text/markdown", "fam.documentation.governance.v1",
                session_id=session_id, principal_id=principal_id,
            )

    def _write_file(
        self, owner_id, task_id, path, content, media_type, provenance, *,
        session_id, principal_id,
    ) -> None:
        root = Path(self._loop.preparation(owner_id, task_id).candidate.candidate_workspace)
        for parent in _missing_parents(root, path):
            self._apply(
                owner_id, task_id,
                CandidateOperation(
                    _identity("documentation-operation", task_id, parent),
                    CandidateOperationKind.CREATE_DIRECTORY, parent,
                ),
                None, None, session_id=session_id, principal_id=principal_id,
            )
        before = _optional_digest(root, path)
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = _identity("documentation-artifact", task_id, path, digest)
        artifact = CandidateArtifact(
            artifact_id, CandidateContentKind.TEXT, media_type, digest,
            len(content), f"signed-generator:{provenance}", path,
        )
        operation = CandidateOperation(
            _identity("documentation-operation", task_id, path, digest),
            CandidateOperationKind.CREATE_FILE if before is None
            else CandidateOperationKind.PATCH_FILE,
            path, before, artifact_id,
        )
        self._apply(
            owner_id, task_id, operation, artifact, content,
            session_id=session_id, principal_id=principal_id,
        )

    def _apply(
        self, owner_id, task_id, operation, artifact, content, *,
        session_id, principal_id,
    ) -> None:
        edit_id = f"edit-{operation.operation_id}"
        prior = next((
            item for item in self._loop.candidate_edits(owner_id, task_id)
            if item.edit_id == edit_id
        ), None)
        if prior is not None:
            operation, artifact = prior.operation, prior.artifact
        record = self._loop.edit_candidate(
            owner_id, task_id, edit_id=edit_id, session_id=session_id,
            principal_id=principal_id, operation=operation,
            artifact=artifact, content=content,
        )
        if record.status is not CandidateEditStatus.APPLIED:
            raise RuntimeError("documentation candidate effect was not applied")


class UnavailableNaturalEngineeringDocumentationCoordinator:
    """Fail relevant tasks truthfully when the active release has no recipes."""

    def __init__(self, policy: DocumentationRequirementPolicy | None = None) -> None:
        self._policy = policy or DocumentationRequirementPolicy()

    def generate(self, owner_id, definition, **_kwargs):
        if self._policy.required_kinds(definition.task.intent):
            raise RuntimeError("signed documentation recipes are unavailable")
        return ()


def _source_content(root, paths, maximum_files, maximum_bytes):
    values = []
    total = 0
    for relative in tuple(dict.fromkeys(paths)):
        if len(values) >= maximum_files:
            break
        try:
            path = _required_file(root, relative)
            content = path.read_bytes()
            content.decode("utf-8", "strict")
        except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeError):
            continue
        if len(content) > maximum_bytes - total:
            continue
        source = DocumentationSource(relative, hashlib.sha256(content).hexdigest())
        values.append(DocumentationSourceContent(source, content))
        total += len(content)
    if not values:
        raise RuntimeError("documentation policy selected no readable sources")
    return tuple(values)


def _missing_parents(root: Path, relative: str) -> tuple[str, ...]:
    values = []
    for parent in reversed(PurePosixPath(relative).parents[:-1]):
        path = root / parent.as_posix()
        if path.exists():
            if not path.is_dir() or path.is_symlink():
                raise PermissionError("documentation output parent is unsafe")
        else:
            values.append(parent.as_posix())
    return tuple(values)


def _required_file(root: Path, relative: str) -> Path:
    resolved = root.resolve(strict=True)
    raw = resolved / relative
    current = raw
    while current != resolved:
        if current.is_symlink():
            raise PermissionError("documentation source uses a symlink")
        current = current.parent
    target = raw.resolve(strict=True)
    if resolved not in target.parents or not target.is_file():
        raise PermissionError("documentation source escapes candidate")
    return target


def _optional_digest(root: Path, relative: str) -> str | None:
    try:
        return hashlib.sha256(_required_file(root, relative).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def _identity(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _governance_content(definition, recipes):
    coordinates = tuple(item.coordinate for item in recipes)
    recipe_lines = "\n".join(f"- `{item}`" for item in coordinates) + "\n"
    ownership = (
        "# FAM_OS generated-content ownership\n\n"
        f"Task: `{definition.task.task_id}`\n\n"
        "Generated artifacts in this task are owned by the repository owner "
        "and must be regenerated through the signed recipes below.\n\n"
        + recipe_lines
    ).encode()
    regeneration = (
        "# Authoritative regeneration\n\n"
        "Do not edit generated outputs directly. Resume the owning FAM_OS "
        f"engineering task `{definition.task.task_id}` so Core can rerun the "
        "release-signed recipe and reverify the resulting changeset.\n\n"
        + recipe_lines
    ).encode()
    requirements = (
        "# Owner-approved engineering requirement\n\n"
        f"Task: `{definition.task.task_id}`\n\n"
        f"Task digest: `{definition.task_sha256}`\n\n"
        f"Acceptance policy: `{definition.acceptance_policy_id}`\n\n"
        "The exact owner intent remains in owner-private task state. This file "
        "is the repository trace anchor and intentionally contains no prompt, "
        "credential, or private user data.\n"
    ).encode()
    return (
        (DOCUMENTATION_OWNERSHIP_PATH, ownership),
        (DOCUMENTATION_REGENERATION_PATH, regeneration),
        (DOCUMENTATION_REQUIREMENTS_PATH, requirements),
    )
