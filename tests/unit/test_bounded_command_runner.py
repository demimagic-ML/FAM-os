import sys
import unittest
from pathlib import Path

from fam_os.adapters.linux.bounded_command import (
    BoundedCommandPolicy, BoundedSubprocessRunner,
)


class BoundedCommandRunnerTests(unittest.TestCase):
    def test_runs_exact_arguments_without_shell(self):
        runner = BoundedSubprocessRunner()
        result = runner.run((
            sys.executable, "-c", "import sys; print(sys.argv[1])", "$(touch never)",
        ))
        self.assertTrue(result.succeeded)
        self.assertEqual("$(touch never)\n", result.stdout)

    def test_output_limit_and_timeout_terminate_process(self):
        limited = BoundedSubprocessRunner(BoundedCommandPolicy(
            timeout_seconds=1, maximum_stdout_bytes=10, maximum_stderr_bytes=10
        )).run((sys.executable, "-c", "print('x' * 1000)"))
        self.assertTrue(limited.output_limited)
        self.assertLessEqual(len(limited.stdout.encode()), 10)

        timed = BoundedSubprocessRunner(BoundedCommandPolicy(
            timeout_seconds=0.05, maximum_stdout_bytes=100, maximum_stderr_bytes=100
        )).run((sys.executable, "-c", "import time; time.sleep(5)"))
        self.assertTrue(timed.timed_out)

    def test_requires_absolute_executable_and_explicit_safe_environment(self):
        runner = BoundedSubprocessRunner()
        with self.assertRaisesRegex(ValueError, "absolute"):
            runner.run(("python3", "-V"))
        with self.assertRaisesRegex(ValueError, "environment"):
            runner.run((sys.executable, "-V"), environment={"BAD=KEY": "x"})
        with self.assertRaisesRegex(ValueError, "working directory"):
            runner.run((sys.executable, "-V"), cwd=Path("relative"))


if __name__ == "__main__":
    unittest.main()
