"""Opt-in live proof of ChatGPT-authenticated GPT-5.6-Sol inference."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from fam_os.adapters.codex_subscription import (
    CodexSubscriptionRuntime, CodexSubscriptionSettings,
)
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
)


class CodexSubscriptionSmokeTests(unittest.TestCase):
    def test_chatgpt_authenticated_sol_returns_effect_free_json(self):
        if os.environ.get("FAM_RUN_CODEX_SUBSCRIPTION_SMOKE") != "1":
            self.skipTest("set FAM_RUN_CODEX_SUBSCRIPTION_SMOKE=1")
        executable = shutil.which("codex")
        if executable is None:
            self.skipTest("Codex CLI is unavailable")
        with tempfile.TemporaryDirectory(
            prefix="fam-codex-subscription-smoke-",
        ) as temporary:
            runtime = CodexSubscriptionRuntime(CodexSubscriptionSettings(
                Path(executable).absolute(), Path(temporary) / "work",
                Path.home().absolute(),
            ))
            response = runtime.chat(InferenceRequest(
                "gpt-5.6-sol",
                (
                    InferenceMessage(
                        MessageRole.SYSTEM,
                        "Return only a JSON object with status and model.",
                    ),
                    InferenceMessage(
                        MessageRole.USER,
                        "Set status to connected and model to gpt-5.6-sol.",
                    ),
                ),
                2_048, 512, json_output=True,
            ))
        self.assertEqual({
            "status": "connected", "model": "gpt-5.6-sol",
        }, json.loads(response.content))
        self.assertGreater(response.metrics.prompt_tokens, 0)
        self.assertGreater(response.metrics.output_tokens, 0)


if __name__ == "__main__":
    unittest.main()
