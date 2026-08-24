import base64
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.bubblewrap.engineering import EngineeringSandboxAdapter
from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier
from fam_os.adapters.filesystem.candidate_workspace import CandidateWorkspaceAdapter
from fam_os.adapters.git import LocalGitAdapter
from fam_os.adapters.media.design_assets import DesignAssetSanitizer
from fam_os.core.engineering import (
    CandidateWorkspace,
    EngineeringEcosystem,
    EngineeringSandboxProfile,
    SandboxNetworkMode,
    SignedToolRecipe,
    ToolQualificationStatus,
    ToolRecipePurpose,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog, signed_recipe_payload
from fam_os.product.bundle_installation import _extract


NOW = datetime(2026, 7, 18, tzinfo=timezone.utc)


class EngineeringAdversarialTests(unittest.TestCase):
    def test_candidate_rejects_symlink_and_hardlink_races(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            owner, transactions = root / "owner", root / "transactions"
            owner.mkdir()
            source = owner / "source.txt"
            source.write_text("trusted")
            os.link(source, owner / "alias.txt")
            with self.assertRaisesRegex(PermissionError, "hardlinked"):
                CandidateWorkspaceAdapter(owner, transactions)
            (owner / "alias.txt").unlink()
            (owner / "escape").symlink_to("/tmp")
            with self.assertRaisesRegex(PermissionError, "symbolic"):
                CandidateWorkspaceAdapter(owner, transactions)

    def test_release_archive_rejects_traversal_links_and_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, member in (
                ("traversal", tarfile.TarInfo("../escape")),
                ("link", tarfile.TarInfo("linked")),
            ):
                archive = root / f"{name}.tar"
                if name == "traversal":
                    member.size = 0
                else:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/etc/passwd"
                with tarfile.open(archive, "w") as output:
                    output.addfile(member)
                with self.assertRaises(ValueError):
                    _extract(archive, root / f"output-{name}")

    def test_malicious_svg_external_content_and_decompression_bomb_fail_closed(self):
        sanitizer = DesignAssetSanitizer(maximum_pixels=100)
        for content in (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>',
        ):
            with self.assertRaises(ValueError):
                sanitizer.sanitize_svg(content)

    def test_network_exfiltration_output_flood_and_fork_pressure_are_contained(self):
        private = Ed25519PrivateKey.generate()
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({
            "security-key": private.public_key(),
        }))
        profile = EngineeringSandboxProfile(
            "adversarial", 256 * 1024**2, 2, 5, 8, 1024, 1024**2,
            SandboxNetworkMode.DENIED, (), (("PATH", "/usr/bin:/bin"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate = CandidateWorkspace(
                "security-candidate", "security-task", "baseline", "/owner",
                str(root), NOW, "full_copy_fallback", "a" * 64, (),
            )
            adapter = EngineeringSandboxAdapter(catalog)
            cases = {
                "network": "import socket; socket.create_connection(('1.1.1.1',53),.1)",
                "flood": "print('x'*1000000)",
                "fork": "import os,time,sys\nfor _ in range(64):\n try:\n  p=os.fork()\n  if p==0: time.sleep(2); os._exit(0)\n except OSError: sys.exit(9)",
            }
            for identity, program in cases.items():
                recipe = _recipe(private, identity, program)
                catalog.admit(recipe)
                receipt = adapter.run(
                    "security-task", candidate, recipe.recipe_id,
                    recipe.recipe_version, profile,
                )
                self.assertIsNot(
                    ToolQualificationStatus.PASSED, receipt.status,
                    f"adversarial case unexpectedly passed: {identity}",
                )


def _recipe(private, identity, program):
    placeholder = SignedToolRecipe(
        f"security-{identity}", "1.0.0", EngineeringEcosystem.PYTHON,
        ToolRecipePurpose.STATIC_ANALYSIS, "/usr/bin/python3", ("-c", program),
        ("PATH",), (0,), (f"verifier.security.{identity}",),
        "security-key", "0" * 64, base64.b64encode(b"0" * 64).decode(),
    )
    payload = signed_recipe_payload(placeholder)
    return replace(
        placeholder, payload_sha256=hashlib.sha256(payload).hexdigest(),
        signature_base64=base64.b64encode(private.sign(payload)).decode(),
    )


if __name__ == "__main__":
    unittest.main()
