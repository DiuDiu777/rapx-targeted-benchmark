import importlib.util
import unittest
from pathlib import Path


RUNNER = Path(__file__).parents[1] / "scripts" / "run_one.py"
SPEC = importlib.util.spec_from_file_location("run_one", RUNNER)
run_one = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_one)


class ParseResultsTest(unittest.TestCase):
    def test_counts_finished_unknown_and_not_run(self):
        log = """
        00|RAPx|INFO|: [rapx::verify] total: 1 free function(s), 3 method(s), 0 struct(s), 0 trait(s)
        00|RAPx|INFO|: [rapx::verify] function: one
        00|RAPx|INFO|: result: SOUND
        00|RAPx|INFO|: [rapx::verify] function: two
        00|RAPx|WARN|: result: UNSOUND
        00|RAPx|INFO|: [rapx::verify] function: three
        """
        result = run_one.parse_log(log, 10)
        self.assertEqual(result["active_targets"], 4)
        self.assertEqual(
            result["counts"],
            {"SOUND": 1, "UNSOUND": 1, "UNKNOWN": 1, "NOT_RUN": 1},
        )


if __name__ == "__main__":
    unittest.main()
