"""Assemble a candidate with verifier-owned deterministic tests."""

from fam_os.verification.python.bundles import TrustedPythonTests


PASS_SENTINEL = "FAM_PYTHON_VERIFICATION_PASS_V1"


def build_verification_script(candidate: str, tests: TrustedPythonTests) -> str:
    disclosed = f"__FAM_CANDIDATE_SOURCE__ = {candidate!r}"
    return (
        f"{disclosed}\n\n{candidate}\n\n{tests.source}\n\n"
        f"print({PASS_SENTINEL!r})\n"
    )
