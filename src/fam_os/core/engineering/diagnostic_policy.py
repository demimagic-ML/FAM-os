"""Admission policy binding runtime-diagnostic kinds to signed recipes."""

from fam_os.core.engineering.diagnostics import (
    RuntimeDiagnosticKind,
    RuntimeDiagnosticRequest,
)
from fam_os.core.engineering.execution import SignedToolRecipe, ToolRecipePurpose
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering._validation import relative_path


DIAGNOSTIC_PURPOSES = {
    RuntimeDiagnosticKind.STACK_TRACE: ToolRecipePurpose.STACK_TRACE,
    RuntimeDiagnosticKind.CRASH_DUMP: ToolRecipePurpose.CRASH_DUMP,
    RuntimeDiagnosticKind.TRACE: ToolRecipePurpose.TRACE,
    RuntimeDiagnosticKind.CPU_PROFILE: ToolRecipePurpose.CPU_PROFILE,
    RuntimeDiagnosticKind.MEMORY_PROFILE: ToolRecipePurpose.MEMORY_PROFILE,
    RuntimeDiagnosticKind.RACE_DETECTION: ToolRecipePurpose.RACE_DETECTION,
    RuntimeDiagnosticKind.LEAK_DETECTION: ToolRecipePurpose.LEAK_DETECTION,
    RuntimeDiagnosticKind.PERFORMANCE_REGRESSION: ToolRecipePurpose.PERFORMANCE_REGRESSION,
}


class RuntimeDiagnosticRecipePolicy:
    def __init__(self, catalog: SignedToolRecipeCatalog) -> None:
        self._catalog = catalog

    def admit(self, request: RuntimeDiagnosticRequest) -> SignedToolRecipe:
        recipe = self._catalog.get(
            request.signed_recipe_id,
            request.signed_recipe_version,
        )
        if recipe.payload_sha256 != request.recipe_payload_sha256:
            raise PermissionError("runtime diagnostic recipe digest is mismatched")
        if recipe.purpose is not DIAGNOSTIC_PURPOSES[request.kind]:
            raise PermissionError("signed recipe purpose does not match diagnostic kind")
        if recipe.network_mode is not request.network_mode:
            raise PermissionError("diagnostic recipe and request network policies differ")
        if set(request.allowed_environment_keys) - set(recipe.allowed_environment_keys):
            raise PermissionError("diagnostic request widens the signed environment")
        return recipe

    def resolve_argv(
        self,
        request: RuntimeDiagnosticRequest,
        recipe: SignedToolRecipe,
    ) -> tuple[str, ...]:
        if len(request.target_argv) != 1:
            raise PermissionError("runtime diagnostics require one exact target path")
        target = request.target_argv[0]
        relative_path(target, "diagnostic target")
        if recipe.argv_template.count("{diagnostic_target}") != 1:
            raise PermissionError("signed diagnostic recipe requires one target placeholder")
        sandbox_target = "/workspace/" + target
        return tuple(
            sandbox_target if value == "{diagnostic_target}" else value
            for value in recipe.argv_template
        )
