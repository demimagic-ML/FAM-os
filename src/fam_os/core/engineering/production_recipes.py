"""Release-owned recipe specifications for the initial engineering matrix."""

from dataclasses import dataclass

from fam_os.core.engineering.execution import (
    EngineeringEcosystem,
    ToolRecipePurpose,
)
from fam_os.core.engineering.recipe_matrix import REQUIRED_PURPOSES


@dataclass(frozen=True, slots=True)
class ToolRecipeSpecification:
    ecosystem: EngineeringEcosystem
    purpose: ToolRecipePurpose
    executable_path: str
    argv: tuple[str, ...]
    verifier_id: str
    recipe_id: str | None = None


_TOOLS = {
    EngineeringEcosystem.PYTHON: ("/usr/bin/python3", ("-m", "compileall", "-q", ".")),
    EngineeringEcosystem.JAVASCRIPT: ("/usr/bin/node", ("--check", "index.js")),
    EngineeringEcosystem.TYPESCRIPT: ("/opt/fam/toolchains/typescript/bin/tsc", ("--noEmit",)),
    EngineeringEcosystem.RUST: ("/opt/fam/toolchains/rust/bin/cargo", ("check", "--offline", "--locked")),
    EngineeringEcosystem.GO: ("/opt/fam/toolchains/go/bin/go", ("test", "./...")),
    EngineeringEcosystem.JAVA: ("/usr/bin/javac", ("Main.java",)),
    EngineeringEcosystem.KOTLIN: ("/opt/fam/toolchains/kotlin/bin/kotlinc", ("Main.kt", "-d", "/tmp/main.jar")),
    EngineeringEcosystem.C: ("/usr/bin/gcc", ("-Wall", "-Wextra", "-Werror", "-fsyntax-only", "main.c")),
    EngineeringEcosystem.CPP: ("/usr/bin/g++", ("-Wall", "-Wextra", "-Werror", "-fsyntax-only", "main.cpp")),
    EngineeringEcosystem.SHELL: ("/usr/bin/bash", ("-n", "main.sh")),
    EngineeringEcosystem.HTML: ("/usr/bin/python3", ("/opt/fam/toolchains/web/web_quality.py", "html", "index.html")),
    EngineeringEcosystem.CSS: ("/usr/bin/python3", ("/opt/fam/toolchains/web/web_quality.py", "css", "styles.css")),
}


def initial_recipe_specifications() -> tuple[ToolRecipeSpecification, ...]:
    """Return a decision-complete recipe coordinate for every required gate."""
    values = []
    for ecosystem in EngineeringEcosystem:
        executable, baseline = _TOOLS[ecosystem]
        for purpose in sorted(REQUIRED_PURPOSES[ecosystem], key=lambda item: item.value):
            values.append(ToolRecipeSpecification(
                ecosystem,
                purpose,
                executable,
                _purpose_argv(ecosystem, purpose, baseline),
                f"verifier.engineering.{ecosystem.value}.{purpose.value}.v1",
            ))
    return tuple(values)


def diagnostic_recipe_specifications() -> tuple[ToolRecipeSpecification, ...]:
    """Return release-owned diagnostic recipes with one typed target path."""
    target = "{diagnostic_target}"
    tool = "/opt/fam/toolchains/diagnostics/tool.py"
    values = (
        (ToolRecipePurpose.STACK_TRACE, "/usr/bin/python3", (tool, "stack", target)),
        (ToolRecipePurpose.CRASH_DUMP, "/usr/bin/python3", (tool, "core", target)),
        (
            ToolRecipePurpose.TRACE, "/usr/bin/strace",
            ("-f", "--", "/usr/bin/python3", tool, "run", target),
        ),
        (ToolRecipePurpose.CPU_PROFILE, "/usr/bin/python3", ("-m", "cProfile", target)),
        (ToolRecipePurpose.MEMORY_PROFILE, "/usr/bin/time", ("-v", "/usr/bin/python3", target)),
        (ToolRecipePurpose.RACE_DETECTION, "/usr/bin/python3", (tool, "race", target)),
        (ToolRecipePurpose.LEAK_DETECTION, "/usr/bin/python3", (tool, "leak", target)),
        (
            ToolRecipePurpose.PERFORMANCE_REGRESSION, "/usr/bin/time",
            ("-p", "/usr/bin/python3", tool, "run", target),
        ),
    )
    return tuple(
        ToolRecipeSpecification(
            EngineeringEcosystem.C, purpose, executable, argv,
            f"verifier.engineering.runtime.{purpose.value}.v1",
        )
        for purpose, executable, argv in values
    )


def _purpose_argv(ecosystem, purpose, baseline):
    # Each coordinate is explicit even where a compiler-backed gate serves more
    # than one purpose. Install-time qualification proves the exact executable.
    specialized = {
        (EngineeringEcosystem.PYTHON, ToolRecipePurpose.TEST): ("-m", "unittest", "discover", "-v"),
        (EngineeringEcosystem.PYTHON, ToolRecipePurpose.PACKAGE): ("-m", "build", "--no-isolation"),
        (EngineeringEcosystem.JAVASCRIPT, ToolRecipePurpose.TEST): ("--test",),
        (EngineeringEcosystem.JAVASCRIPT, ToolRecipePurpose.PACKAGE): ("/workspace/package.json",),
        (EngineeringEcosystem.TYPESCRIPT, ToolRecipePurpose.BUILD): ("--build", "--pretty", "false"),
        (EngineeringEcosystem.RUST, ToolRecipePurpose.TEST): ("test", "--offline", "--locked"),
        (EngineeringEcosystem.RUST, ToolRecipePurpose.BUILD): ("build", "--offline", "--locked"),
        (EngineeringEcosystem.RUST, ToolRecipePurpose.PACKAGE): ("package", "--offline", "--locked"),
        (EngineeringEcosystem.GO, ToolRecipePurpose.BUILD): ("build", "./..."),
        (EngineeringEcosystem.GO, ToolRecipePurpose.COVERAGE): ("test", "-cover", "./..."),
    }
    return specialized.get((ecosystem, purpose), baseline)
