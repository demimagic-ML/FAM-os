import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.core.ports import InferenceResponse
from fam_os.core.lifecycle import FinalResultPolicy
from fam_os.applications import (
    WORKSPACE_MAP_CAPABILITY, WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.shell import (
    ShellAskCommand, ShellContext, ShellContextKind, ShellDecision,
    ShellDecisionCommand,
)
from fam_os.telemetry import InferenceMetrics
from tests.integration.product_runtime_fixture import (
    ContextProfileFixture,
    ResidentRuntimeFixture,
)


class _Runtime(ResidentRuntimeFixture):
    def __init__(self, content="Grounded local result", responses=None):
        super().__init__()
        self.requests = []
        self.content = content
        self.responses = list(responses or ())

    def chat(self, request):
        self.requests.append(request)
        return InferenceResponse(
            self.responses.pop(0) if self.responses else self.content,
            InferenceMetrics(request.model_ref, 0.01, 0.0, 8, 4, 400.0),
        )

class ProductOsWorkflowTests(unittest.TestCase):
    def test_invalid_workspace_candidate_is_repaired_with_exact_core_feedback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            project = home / "project"
            source = project / "src/app.py"
            source.parent.mkdir(parents=True)
            source.write_text('GREETING = "old"\n')
            runtime = _Runtime(responses=(
                json.dumps({
                    "plan": ["Change an unobserved file."],
                    "changes": [{"path": "src/missing.py", "content": "bad\n"}],
                }),
                json.dumps({
                    "plan": ["Change the observed greeting."],
                    "changes": [{
                        "path": "src/app.py", "content": 'GREETING = "new"\n',
                    }],
                }),
            ))
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(
                    settings, runtime,
                    context_profile_observer=ContextProfileFixture(),
                )
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(_workspace_command(project))
                approval = _approval(client, accepted.session_id)

                self.assertEqual(2, len(runtime.requests))
                repair_prompt = runtime.requests[1].messages[-1].content
                self.assertIn("[workspace-parameter-repair]", repair_prompt)
                self.assertIn("src/app.py", repair_prompt)
                self.assertIn("only an observed document", repair_prompt)
                self.assertEqual(2048, runtime.requests[1].max_output_tokens)
                self.assertEqual('GREETING = "old"\n', source.read_text())
                client.decide(ShellDecisionCommand(
                    accepted.session_id, approval.revision,
                    approval.approval.approval_id, ShellDecision.APPROVE,
                ))
                result = _terminal(client, accepted.session_id)
                self.assertTrue(result.result.verified)
                self.assertEqual('GREETING = "new"\n', source.read_text())
            finally:
                service.stop()

    def test_workspace_candidate_can_fail_honestly_when_scope_is_unsupported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            project = home / "project"
            project.mkdir(parents=True)
            source = project / "app.py"
            source.write_text("VALUE = 1\n")
            runtime = _Runtime(json.dumps({
                "unavailable_reason": "The request needs several new files.",
            }))
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(
                    settings, runtime,
                    context_profile_observer=ContextProfileFixture(),
                )
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                accepted = client.ask(_workspace_command(project))
                result = _terminal(client, accepted.session_id)

                self.assertIn("No action was executed", result.result.reason)
                self.assertIn("iterative workspace agent", result.result.reason)
                repositories = service._storage_unit.core.repositories()
                plan = repositories.plans.get(accepted.session_id)
                core_result = FinalResultPolicy(
                    repositories.final_evidence,
                ).assemble(plan).result
                self.assertEqual(
                    "application.action.scope_unsupported",
                    core_result.failure.code,
                )
                self.assertEqual("VALUE = 1\n", source.read_text())
                self.assertEqual(1, len(runtime.requests))
            finally:
                service.stop()

    def test_console_shaped_workspace_request_plans_previews_applies_and_reobserves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            project = home / "project"
            source = project / "src/app.py"
            source.parent.mkdir(parents=True)
            source.write_text('GREETING = "old"\n')
            (project / "AGENTS.md").write_text("Modify only observed files.\n")
            runtime = _Runtime(json.dumps({
                "plan": ["Update the greeting constant in the observed application file."],
                "changes": [{
                    "path": "src/app.py", "content": 'GREETING = "new"\n',
                }],
            }))
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(
                    settings, runtime,
                    context_profile_observer=ContextProfileFixture(),
                )
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                capabilities = (
                    "os.directory.inspect", "os.directory.list", "os.file.read",
                    "os.directory.create", "os.directory.remove-empty",
                    WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
                    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
                )
                accepted = client.ask(ShellAskCommand(
                    "workspace-implement",
                    "Create a plan to update the greeting and implement it.",
                    (
                        ShellContext(
                            "filesystem", ShellContextKind.APPLICATION,
                            "owner-filesystem", "Local filesystem", capabilities,
                        ),
                        ShellContext(
                            "workspace", ShellContextKind.URI,
                            project.as_uri() + "/", "project",
                        ),
                    ),
                ))
                approval = _approval(client, accepted.session_id)

                self.assertEqual(
                    "apply_workspace_patch",
                    json.loads(approval.approval.summary)["operation"],
                )
                self.assertEqual('GREETING = "old"\n', source.read_text())
                client.decide(ShellDecisionCommand(
                    accepted.session_id, approval.revision,
                    approval.approval.approval_id, ShellDecision.APPROVE,
                ))
                result = _terminal(client, accepted.session_id)

                execution = service._storage_unit.core.repositories().application_executions.get(
                    accepted.session_id,
                )
                self.assertTrue(result.result.verified, (result, execution))
                self.assertIn(
                    "Approved plan:", result.result.content,
                    (result.result.content, execution.action_result.output),
                )
                self.assertIn("Verified changed files:", result.result.content)
                self.assertIn(
                    "Update observed file src/app.py using the approved diff.",
                    result.result.content,
                )
                self.assertIn("- src/app.py", result.result.content)
                self.assertEqual('GREETING = "new"\n', source.read_text())
                self.assertEqual(1, len(runtime.requests))
                self.assertEqual(
                    "Create a plan to update the greeting and implement it.",
                    runtime.requests[0].messages[-1].content,
                )
                self.assertEqual(4096, runtime.requests[0].max_output_tokens)
                self.assertTrue(runtime.requests[0].json_output)
                self.assertEqual(0.0, runtime.requests[0].temperature)
                self.assertIn(
                    "core.intent.application_mutation",
                    execution.routed.admitted.request.required_capabilities,
                )
                activity = service.shell_server.dispatcher.gateway.application_activity(
                    accepted.session_id,
                )
                self.assertEqual(3, len(activity.observations))
                self.assertTrue(
                    service.shell_server.dispatcher.gateway.reversals.status(
                        accepted.session_id,
                    )["available"],
                )
            finally:
                service.stop()

    def test_selected_owner_folder_is_returned_exactly_without_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            project = home / "project"
            project.mkdir(parents=True)
            (project / "README.md").write_text("# Resident workspace\n")
            runtime = _Runtime()
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
            )
            with patch.dict("os.environ", {"HOME": str(home)}):
                service = LocalProductService(
                    settings, runtime,
                    context_profile_observer=ContextProfileFixture(),
                )
                service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                workspace_uri = project.as_uri() + "/"
                accepted = client.ask(ShellAskCommand(
                    "workspace-list", "What is in this folder?",
                    (
                        ShellContext(
                            "filesystem", ShellContextKind.APPLICATION,
                            "owner-filesystem", "Local filesystem",
                            ("os.directory.inspect", "os.directory.list", "os.file.read"),
                        ),
                        ShellContext(
                            "project", ShellContextKind.URI,
                            workspace_uri, "project",
                        ),
                    ),
                ))
                result = _terminal(client, accepted.session_id)

                self.assertEqual("grounded", result.result.assurance.value)
                self.assertEqual([], runtime.requests)
                self.assertIn('Files (1):\n- "README.md"', result.result.content)
                activity = service.shell_server.dispatcher.gateway.application_activity(
                    accepted.session_id,
                )
                self.assertEqual(2, len(activity.observations))
            finally:
                service.stop()

    def test_file_summary_and_approved_test_run_use_real_os_adapters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            readme = project / "README.md"
            readme.write_text("# Resident Neural Fabric\n")
            state = root / "state"
            (state / "config").mkdir(parents=True)
            config = state / "config/os-tools.json"
            config.write_text(json.dumps(_configuration(project)))
            os.chmod(config, 0o600)
            service = LocalProductService(ProductServiceSettings(
                state, root / "runtime", console_port=0,
            ), _Runtime(), context_profile_observer=ContextProfileFixture())
            service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime/shell.sock", 5,
                ))
                summary = client.ask(_summary_command(readme))
                summary_result = _terminal(client, summary.session_id)
                self.assertEqual("grounded", summary_result.result.assurance.value)
                self.assertEqual("Grounded local result", summary_result.result.content)

                test = client.ask(_test_command())
                approval = _approval(client, test.session_id)
                client.decide(ShellDecisionCommand(
                    test.session_id, approval.revision,
                    approval.approval.approval_id, ShellDecision.APPROVE,
                ))
                test_result = _terminal(client, test.session_id)
                self.assertTrue(test_result.result.verified)
                repositories = service._storage_unit.core.repositories()
                application = repositories.application_executions.get(test.session_id)
                self.assertTrue(application.action_result.verified)
                self.assertEqual(0, application.action_result.output["exit_code"])
            finally:
                service.stop()


def _configuration(project):
    return {
        "contract_version": "fam.product.os-tools/v1alpha1",
        "projects": [{
            "project_id": "demo", "display_name": "Demo project",
            "root": str(project),
            "commands": [{
                "capability_id": "project.test", "display_name": "Run project tests",
                "executable": "/bin/true", "arguments": [],
            }],
        }],
    }


def _application_context():
    return ShellContext(
        "project", ShellContextKind.APPLICATION, "project-demo", "Demo project",
        ("os.file.read", "project.test"),
    )


def _workspace_command(project):
    return ShellAskCommand(
        "workspace-repair", "Implement the requested bounded file change.",
        (
            ShellContext(
                "filesystem", ShellContextKind.APPLICATION,
                "owner-filesystem", "Local filesystem",
                (
                    WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
                    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
                ),
            ),
            ShellContext(
                "workspace", ShellContextKind.URI,
                project.as_uri() + "/", "project",
            ),
        ),
    )


def _summary_command(readme):
    return ShellAskCommand(
        "summary-request", "Summarize this project README.",
        (_application_context(), ShellContext(
            "readme", ShellContextKind.FILE, readme.as_uri(), "README.md",
        )),
        ("os.file.read", "project.test"),
    )


def _test_command():
    return ShellAskCommand(
        "test-request", "Run the project tests.", (_application_context(),),
        ("os.file.read", "project.test"), True,
    )


def _approval(client, session_id):
    deadline = time.monotonic() + 5
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.approval is not None:
            return snapshot
        time.sleep(.01)
    raise AssertionError(f"OS command did not request approval: {snapshot}")


def _terminal(client, session_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.result is not None:
            return snapshot
        time.sleep(.01)
    raise AssertionError("OS workflow did not finish")


if __name__ == "__main__":
    unittest.main()
