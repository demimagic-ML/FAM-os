"""Real positive/failing polyglot fixtures in transient candidate sandboxes."""

import base64
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.bubblewrap.engineering import (
    EngineeringSandboxAdapter, toolchain_tree_sha256,
)
from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.core.engineering import (
    CandidateWorkspace, EngineeringEcosystem, EngineeringSandboxProfile,
    PolyglotQualificationService, SandboxNetworkMode, SignedToolRecipe,
    ToolQualificationStatus, ToolRecipePurpose, ToolchainMount,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog, signed_recipe_payload


NOW = datetime(2026, 7, 18, 20, 0, tzinfo=timezone.utc)
FIXTURES = {
    EngineeringEcosystem.PYTHON: ("main.py", "value: int = 1\n", "def broken(:\n"),
    EngineeringEcosystem.JAVASCRIPT: ("main.js", "const value = 1;\n", "const = ;\n"),
    EngineeringEcosystem.TYPESCRIPT: ("main.ts", "const value: number = 1;\n", "const value: number = 'bad';\n"),
    EngineeringEcosystem.RUST: ("main.rs", "pub fn value() -> i32 { 1 }\n", "pub fn broken( {\n"),
    EngineeringEcosystem.GO: ("main.go", "package main\nfunc main() {}\n", "package main\nfunc broken( {\n"),
    EngineeringEcosystem.JAVA: ("main.java", "class main { public static void main(String[] a) {} }\n", "class main { broken }\n"),
    EngineeringEcosystem.KOTLIN: ("main.kt", "fun value(): Int = 1\n", "fun broken(: Int = 1\n"),
    EngineeringEcosystem.C: ("main.c", "int main(void) { return 0; }\n", "int main( {\n"),
    EngineeringEcosystem.CPP: ("main.cpp", "int main() { return 0; }\n", "int main( {\n"),
    EngineeringEcosystem.SHELL: ("main.sh", "#!/bin/sh\nexit 0\n", "if then\n"),
    EngineeringEcosystem.HTML: ("main.html", "<!doctype html><html><body><p>ok</p></body></html>\n", "<html><body><img></body>\n"),
    EngineeringEcosystem.CSS: ("main.css", "body { color: black; }\n", "body { color: black;\n"),
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def mount(source: Path, target: str) -> ToolchainMount:
    return ToolchainMount(str(source), target, toolchain_tree_sha256(source))


def kotlin_jars() -> tuple[Path, ...]:
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1"
    coordinates = (
        "org.jetbrains.kotlin/kotlin-compiler-embeddable/2.1.0",
        "org.jetbrains.kotlin/kotlin-stdlib/2.1.0",
        "org.jetbrains.kotlin/kotlin-script-runtime/2.1.0",
        "org.jetbrains.kotlin/kotlin-reflect/1.6.10",
        "org.jetbrains.kotlin/kotlin-daemon-embeddable/2.1.0",
        "org.jetbrains.intellij.deps/trove4j/1.0.20200330",
        "org.jetbrains.kotlinx/kotlinx-coroutines-core-jvm/1.6.4",
    )
    return tuple(next((cache / value).glob("*/*.jar")) for value in coordinates)


def recipe_spec(ecosystem, repository_root):
    rust_root = Path(subprocess.run(
        ("rustc", "--print", "sysroot"), check=True, capture_output=True, text=True,
    ).stdout.strip()).resolve()
    go_root = Path("/snap/go/current").resolve()
    typescript = repository_root / "connectors/vscode/node_modules/typescript"
    web = repository_root / "tools/verifiers/web_quality.py"
    values = {
        EngineeringEcosystem.PYTHON: ("/usr/bin/python3", ("-m", "py_compile", "main.py"), ()),
        EngineeringEcosystem.JAVASCRIPT: ("/usr/bin/node", ("--check", "main.js"), ()),
        EngineeringEcosystem.TYPESCRIPT: ("/usr/bin/node", ("/opt/fam/toolchains/typescript/lib/tsc.js", "--strict", "--noEmit", "main.ts"), (mount(typescript, "/opt/fam/toolchains/typescript"),)),
        EngineeringEcosystem.RUST: ("/opt/fam/toolchains/rust/bin/rustc", ("--crate-type", "lib", "main.rs", "-o", "/tmp/main.rlib"), (mount(rust_root, "/opt/fam/toolchains/rust"),)),
        EngineeringEcosystem.GO: ("/opt/fam/toolchains/go/bin/go", ("tool", "compile", "-o", "/tmp/main.o", "main.go"), (mount(go_root, "/opt/fam/toolchains/go"),)),
        EngineeringEcosystem.JAVA: ("/usr/lib/jvm/java-21-openjdk-amd64/bin/java", ("-Xmx128m", "-XX:MaxMetaspaceSize=128m", "-XX:CompressedClassSpaceSize=32m", "main.java"), ()),
        EngineeringEcosystem.C: ("/usr/bin/gcc", ("-fsyntax-only", "main.c"), ()),
        EngineeringEcosystem.CPP: ("/usr/bin/g++", ("-fsyntax-only", "main.cpp"), ()),
        EngineeringEcosystem.SHELL: ("/usr/bin/bash", ("-n", "main.sh"), ()),
        EngineeringEcosystem.HTML: ("/usr/bin/python3", ("/opt/fam/toolchains/web_quality.py", "html", "main.html"), (mount(web, "/opt/fam/toolchains/web_quality.py"),)),
        EngineeringEcosystem.CSS: ("/usr/bin/python3", ("/opt/fam/toolchains/web_quality.py", "css", "main.css"), (mount(web, "/opt/fam/toolchains/web_quality.py"),)),
    }
    if ecosystem is EngineeringEcosystem.KOTLIN:
        mounts = tuple(mount(path, f"/opt/fam/toolchains/kotlin/{path.name}") for path in kotlin_jars())
        return "/usr/lib/jvm/java-21-openjdk-amd64/bin/java", ("-Xmx512m", "-XX:MaxMetaspaceSize=256m", "-XX:CompressedClassSpaceSize=64m", "-cp", "/opt/fam/toolchains/kotlin/*", "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "main.kt", "-d", "/tmp/main.jar"), mounts
    return values[ecosystem]


class PolyglotEngineeringSandboxTests(unittest.TestCase):
    def test_real_toolchains_accept_positive_and_reject_negative_fixtures(self):
        repository_root = Path(__file__).resolve().parents[2]
        private = Ed25519PrivateKey.generate()
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "matrix-key": private.public_key(),
        }))
        profile = EngineeringSandboxProfile(
            "polyglot-sandbox", 4 * 1024**3, 10, 30, 512, 65_536,
            64 * 1024**2, SandboxNetworkMode.DENIED, (),
            (("PATH", "/usr/bin:/bin"), ("LANG", "C.UTF-8"),
             ("GOCACHE", "/tmp/go-cache"), ("GOMODCACHE", "/tmp/go-mod")),
        )
        adapter = EngineeringSandboxAdapter(catalog)
        service = PolyglotQualificationService()
        with tempfile.TemporaryDirectory() as directory:
            transaction_root = Path(directory).resolve()
            for ecosystem, (filename, positive_source, negative_source) in FIXTURES.items():
                executable, argv, mounts = recipe_spec(ecosystem, repository_root)
                placeholder = SignedToolRecipe(
                    f"{ecosystem.value}-fixture", "1.0.0", ecosystem,
                    ToolRecipePurpose.LANGUAGE_DIAGNOSTICS, executable, argv,
                    ("PATH", "LANG", "GOCACHE", "GOMODCACHE"), (0,),
                    (f"verifier.{ecosystem.value}.production",), "matrix-key",
                    "0" * 64, base64.b64encode(b"\0" * 64).decode(), mounts,
                )
                payload = signed_recipe_payload(placeholder)
                signed = replace(
                    placeholder, payload_sha256=digest(payload),
                    signature_base64=base64.b64encode(private.sign(payload)).decode(),
                )
                catalog.admit(signed)
                receipts = []
                for label, source in (("positive", positive_source), ("negative", negative_source)):
                    workspace = transaction_root / ecosystem.value / label
                    workspace.mkdir(parents=True)
                    (workspace / filename).write_text(source, encoding="utf-8")
                    candidate = CandidateWorkspace(
                        f"{ecosystem.value}-{label}", "task-polyglot", "baseline",
                        "/owner", str(workspace), NOW, "full_copy_fallback",
                        digest(b"baseline"), (),
                    )
                    receipts.append(adapter.run(
                        "task-polyglot", candidate, signed.recipe_id,
                        signed.recipe_version, profile,
                    ))
                self.assertEqual(
                    ToolQualificationStatus.PASSED, receipts[0].status,
                    f"{ecosystem}: {receipts[0].diagnostic}",
                )
                self.assertEqual(
                    ToolQualificationStatus.FAILED, receipts[1].status,
                    f"{ecosystem}: {receipts[1].diagnostic}",
                )
                qualification = service.qualify(
                    f"qualification-{ecosystem.value}", ecosystem, executable,
                    "host-qualified", receipts[0], receipts[1], qualified_at=NOW,
                    installed_release_id=os.environ.get(
                        "FAM_ENGINEERING_RELEASE_ID", "source-qualification",
                    ),
                )
                self.assertEqual(ToolQualificationStatus.PASSED, qualification.status)


if __name__ == "__main__":
    unittest.main()
