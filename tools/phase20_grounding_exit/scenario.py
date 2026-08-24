"""Exercise installed identity, project, scope, citation, and restart grounding."""

from tools.phase19_exit.console_client import ConsoleClient
from tools.phase20_index_exit.scenario import IndexConsoleClient


def first_process_scenario(service, project_file, private_file) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    client = IndexConsoleClient(base, token)
    no_source = _no_source(client)
    project_receipt = client.create_index({
        "path": str(project_file), "kind": "file", "recursive": False,
        "application_ids": ["fam.shell"], "allowed_extensions": [".md"],
        "expires_in_hours": 24, "confirmed": True,
    })
    private_receipt = client.create_index({
        "path": str(private_file), "kind": "file", "recursive": False,
        "application_ids": ["fam.mcp"], "allowed_extensions": [".txt"],
        "expires_in_hours": 24, "confirmed": True,
    })
    identity = _run(client, "ground-identity", "Explain what FAM_OS is")
    project = _run(client, "ground-project", "Explain this project with citations")
    cross_scope = _run(client, "ground-cross", "search MCP_ONLY_PRIVATE_NONCE")
    return {
        "no_source": no_source,
        "project_receipt": project_receipt,
        "private_receipt": private_receipt,
        "identity": identity,
        "project": project,
        "cross_scope": cross_scope,
    }


def restarted_process_scenario(service) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    client = ConsoleClient(base, token)
    return _run(client, "ground-restart", "Explain this project with citations")


def _run(client: ConsoleClient, request_id: str, prompt: str) -> dict:
    accepted = client.create(request_id, prompt, [], [], False)
    terminal = client.wait_for_terminal(accepted["session_id"])
    result = terminal["result"]
    if result is None or result["status"] != "verified":
        raise RuntimeError(f"installed grounded task failed: {terminal}")
    runs = client.verifications(accepted["session_id"])
    return {
        "request_id": request_id,
        "status": result["status"],
        "assurance": result["assurance"],
        "content": result["content"],
        "citations": result["citations"],
        "verification_runs": runs,
    }


def _no_source(client: ConsoleClient) -> bool:
    try:
        client.create("ground-missing", "Explain this project with citations", [], [], False)
    except RuntimeError as error:
        detail = str(error)
        return "400" in detail and "No active approved local source" in detail
    return False
