"""Same-candidate trusted peer and real remote Gemma scenario."""

from __future__ import annotations

from pathlib import Path

from tools.phase21_peer_exit.release_environment import PeerExitInstallations
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario
from tools.phase21_remote_exit.scenario import run_remote_scenario
from tools.phase21_remote_exit.validation import phase21_4_passed


def run_candidate_remote_scenario(
    *, candidate, desktop, server, repository: Path, root: Path,
    ollama_url: str,
) -> dict[str, object]:
    pair = PeerExitInstallations(
        desktop, server, candidate.manifest,
        candidate.trusted_key_path, candidate.key_id,
    )
    paired = run_installed_peer_scenario(
        pair, repository, root, ollama_url=ollama_url,
    )
    scenario = run_remote_scenario(
        pair, repository, root, paired, ollama_url=ollama_url,
    )
    document = {
        "release_id": candidate.manifest.release_id,
        "signer_key_id": candidate.key_id,
        "release_component_count": len(candidate.manifest.components),
        "desktop_install_healthy": desktop.diagnose().healthy,
        "server_install_healthy": server.diagnose().healthy,
        "pairing_codes_match": paired["pairing_codes_match"],
        "same_host_limitation": True,
        "scenario": scenario,
    }
    document["passed"] = phase21_4_passed(document)
    return document
