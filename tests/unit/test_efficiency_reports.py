import unittest

from fam_os.experts.efficiency_reports import (
    EfficiencyMetric, ExpertEfficiencyMeasurement, PowerSample, build_efficiency_report,
)


def measurement(expert, quality, size, seconds, joules):
    return ExpertEfficiencyMeasurement(
        expert, expert, "a" * 64, quality, size, seconds, joules,
        (PowerSample(0, 10), PowerSample(seconds, 10)),
    )


class EfficiencyReportTests(unittest.TestCase):
    def test_each_metric_selects_from_exact_measurements(self):
        report = build_efficiency_report(
            "r", "meter", "benchmark",
            (measurement("small", .8, 10, 4, 40),
             measurement("fast", 1, 20, 1, 10)),
        )
        selected = {item.metric: item.selected_expert_id for item in report.selections}
        self.assertEqual("small", selected[EfficiencyMetric.QUALITY_PER_BYTE])
        self.assertEqual("fast", selected[EfficiencyMetric.QUALITY_PER_SECOND])
        self.assertEqual("fast", selected[EfficiencyMetric.QUALITY_PER_JOULE])


if __name__ == "__main__":
    unittest.main()
