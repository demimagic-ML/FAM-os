import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.product.agent_usage import AgentUsageRepository, UsageTelemetryRuntime
from fam_os.core.ports.inference import InferenceResponse
from fam_os.telemetry import InferenceMetrics


class _Runtime:
    def chat(self, _request):
        return InferenceResponse("ok", InferenceMetrics("qwen", 2.0, 0.1, 12, 8))

    def loaded_models(self):
        return ("delegated",)


class AgentUsageTests(unittest.TestCase):
    def test_records_real_metrics_and_projects_omarchy_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = AgentUsageRepository(Path(directory) / "usage.sqlite3")
            runtime = UsageTelemetryRuntime(_Runtime(), repository, "ollama")
            self.assertEqual(runtime.chat(object()).content, "ok")
            self.assertEqual(runtime.loaded_models(), ("delegated",))
            record = repository.omarchy_record(datetime.now(timezone.utc))
            self.assertEqual(record["schemaVersion"], 1)
            self.assertEqual(record["id"], "fam-os")
            self.assertEqual(record["todayPrompts"], 1)
            self.assertEqual(record["todayTotalTokens"], 20)
            self.assertEqual(record["modelUsage"]["qwen"]["inputTokens"], 12)
            self.assertEqual(record["modelUsage"]["qwen"]["outputTokens"], 8)
            self.assertEqual(record["providerUsage"]["ollama"]["totalTokens"], 20)
            self.assertEqual(record["inferenceLocation"]["localTokens"], 20)
            self.assertEqual(record["inferenceLocation"]["hostedTokens"], 0)
            self.assertEqual(record["activeSeconds"], 2.0)
            self.assertFalse(record["cacheUsage"]["available"])
            self.assertEqual((Path(directory) / "usage.sqlite3").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
