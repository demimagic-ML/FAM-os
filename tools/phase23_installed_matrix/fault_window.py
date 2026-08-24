#!/usr/bin/env python3
"""Inject the exact post-mutation/pre-result crash window while offline."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import fam_os
from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.product.restart_recovery import PersistedActionState
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.shell import ShellDecision, ShellDecisionCommand


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--ollama-url", required=True)
    parser.add_argument("--source-model-root", type=Path, required=True)
    parser.add_argument("--installation-prefix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    module = Path(fam_os.__file__).resolve()
    if not module.is_relative_to(arguments.installation_prefix.resolve()):
        raise RuntimeError("fault-window product module is not candidate-installed")
    service = LocalProductService(ProductServiceSettings(
        state_root=arguments.state_root,
        runtime_root=arguments.runtime_root,
        console_port=0, manage_ollama=False,
        ollama_url=arguments.ollama_url,
        source_model_root=arguments.source_model_root,
    ), runtime=OllamaRuntime(OllamaSettings(arguments.ollama_url, 30)))
    try:
        service.start()
        shell_server = service.shell_server
        storage = service._storage_unit
        if shell_server is None or storage is None or storage.core is None:
            raise RuntimeError("candidate product composition is incomplete")
        gateway = shell_server.dispatcher.gateway
        snapshot = gateway.snapshot(arguments.session_id)
        if snapshot.approval is None:
            raise RuntimeError("fault-window task is not awaiting approval")
        gateway._application_gateway.decide(ShellDecisionCommand(
            snapshot.session_id, snapshot.revision,
            snapshot.approval.approval_id, ShellDecision.APPROVE,
        ))
        repositories = storage.core.repositories()
        application = repositories.application_executions.get(arguments.session_id)
        if application is None or application.proposal is None:
            raise RuntimeError("fault-window application proposal is unavailable")
        action_id = f"action-{application.proposal.proposal_id}"
        action = repositories.actions.get(action_id)
        if action is None or not repositories.actions.replace(
            action.state, replace(action, state=PersistedActionState.INVOKING),
        ):
            raise RuntimeError("fault-window action state could not enter invoking")
        arguments.target.mkdir(mode=0o700)
        document = {
            "action_id": action_id,
            "candidate_module": str(module),
            "candidate_module_from_install": module.is_relative_to(
                arguments.installation_prefix.resolve()
            ),
            "state": "invoking",
            "target_created": arguments.target.is_dir(),
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(document, sort_keys=True) + "\n")
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
