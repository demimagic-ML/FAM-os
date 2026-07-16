"""Authenticated FAM Shell runner for Phase 5.12 acceptance."""

import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.shell import (
    ShellRequestDispatcher, UnixShellClientConfiguration, UnixShellCoreClient,
    UnixShellServer, UnixShellServerConfiguration,
)
from fam_os.application_acceptance.contracts import AcceptanceReport
from fam_os.application_acceptance.reporting import host_profile, write_report
from fam_os.application_acceptance.shell_gateway import AcceptanceShellGateway
from fam_os.applications.transport import PeerAuthorizationPolicy
from fam_os.shell import ShellController, TerminalShell


class Phase5AcceptanceRunner:
    def __init__(self, root: Path, output: Path):
        self.root = root.resolve(strict=True)
        self.output = output.resolve()

    def run(self):
        with tempfile.TemporaryDirectory(prefix="fam-phase5-acceptance-") as raw:
            workspace = Path(raw)
            os.chmod(workspace, 0o700)
            target = workspace / "acceptance.txt"
            target.write_text("Before\n", encoding="utf-8")
            full, full_transcript = self._mode(workspace, target, True)
            reduced, reduced_transcript = self._mode(workspace, target, False)
        scenarios = tuple((*full, *reduced))
        report = AcceptanceReport(
            f"phase5-{uuid4()}", datetime.now(timezone.utc).isoformat(),
            host_profile(self.root), scenarios, _summarize(scenarios),
            _exit_gate(scenarios),
        )
        transcripts = {"full": full_transcript, "mcp_unavailable": reduced_transcript}
        write_report(self.output, report, transcripts)
        return report

    def _mode(self, workspace, target, mcp_available):
        gateway = AcceptanceShellGateway(
            self.root, workspace, target, mcp_available,
        )
        with tempfile.TemporaryDirectory(prefix="fam-shell-") as raw:
            directory = Path(raw)
            os.chmod(directory, 0o700)
            path = directory / "shell.sock"
            server = UnixShellServer(
                UnixShellServerConfiguration(path),
                PeerAuthorizationPolicy(os.geteuid()),
                ShellRequestDispatcher(gateway),
            )
            server.open()
            try:
                controller = ShellController(
                    UnixShellCoreClient(UnixShellClientConfiguration(
                        path, timeout_seconds=120,
                    )),
                )
                shell = TerminalShell(controller)
                transcript = []
                prompts = (
                    "summarize the current project README",
                ) if not mcp_available else (
                    "summarize the current project README",
                    "run the application action contract test",
                    "edit the temporary acceptance file",
                )
                for prompt in prompts:
                    transcript.extend(self._scenario(server, shell, controller, prompt))
                return tuple(gateway.completed), tuple(transcript)
            finally:
                gateway.close()
                server.close()

    @staticmethod
    def _scenario(server, shell, controller, prompt):
        outputs = []
        outputs.append(_serve(server, lambda: shell.execute(f"ask {prompt}"))[0])
        outputs.append(_serve(server, lambda: shell.execute("refresh"))[0])
        if controller.snapshot.approval is not None:
            outputs.append(_serve(server, lambda: shell.execute("approve"))[0])
        return outputs


def _serve(server, operation):
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    try:
        return operation()
    finally:
        thread.join(timeout=180)
        if thread.is_alive():
            raise TimeoutError("FAM Shell request did not complete")


def _exit_gate(scenarios):
    full = tuple(item for item in scenarios if not item.reduced_fidelity)
    reduced = tuple(item for item in scenarios if item.reduced_fidelity)
    levels = {
        measurement.level for scenario in full for measurement in scenario.measurements
        if measurement.succeeded
    }
    return (
        len(full) == 3 and all(item.succeeded for item in full)
        and any(item.verified for item in full)
        and {"native_semantic", "mcp", "deterministic_os_tool", "accessibility"}
        <= {item.value for item in levels}
        and len(reduced) == 1 and reduced[0].succeeded
    )


def _summarize(scenarios):
    grouped = {}
    for scenario in scenarios:
        for item in scenario.measurements:
            grouped.setdefault(item.level.value, []).append(item)
    return {
        level: {
            "attempts": len(values),
            "successes": sum(item.succeeded for item in values),
            "success_rate": sum(item.succeeded for item in values) / len(values),
            "latency_ms_total": sum(item.latency_ms for item in values),
            "context_bytes_total": sum(item.context_bytes for item in values),
            "cpu_ms_total": sum(item.cpu_ms for item in values),
            "read_bytes_total": sum(item.read_bytes for item in values),
            "write_bytes_total": sum(item.write_bytes for item in values),
            "maximum_rss_bytes": max(
                max(item.rss_before_bytes, item.rss_after_bytes) for item in values
            ),
        }
        for level, values in sorted(grouped.items())
    }
