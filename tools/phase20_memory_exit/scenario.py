"""Exercise same-session, cross-session, and restart memory boundaries."""

from tools.phase19_exit.console_client import ConsoleClient


def first_process_scenario(service) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    conversation = ConsoleClient(base, token)
    isolated = ConsoleClient(base, token)
    tasks = (
        _run(conversation, "memory-first", "My private codename is ORBIT."),
        _run(conversation, "memory-followup", "What is my private codename?"),
        _run(isolated, "memory-isolated", "What is the other session's codename?"),
    )
    return {"tasks": tasks}


def restarted_process_scenario(service) -> dict:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    client = ConsoleClient(base, token)
    return {
        "tasks": (
            _run(client, "memory-after-restart", "What was my private codename?"),
        ),
    }


def _run(client: ConsoleClient, request_id: str, prompt: str) -> dict:
    accepted = client.create(request_id, prompt, [], [], False)
    terminal = client.wait_for_terminal(accepted["session_id"])
    result = terminal["result"]
    if result is None or result["status"] != "completed":
        raise RuntimeError(f"installed memory task failed: {terminal}")
    return {
        "request_id": request_id,
        "session_id": accepted["session_id"],
        "status": result["status"],
        "assurance": result["assurance"],
    }
