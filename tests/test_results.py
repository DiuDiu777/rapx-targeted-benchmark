import importlib.util
import unittest
from pathlib import Path


RUNNER = Path(__file__).parents[1] / "scripts" / "run_one.py"
SPEC = importlib.util.spec_from_file_location("run_one", RUNNER)
run_one = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_one)

RESOLVER = Path(__file__).parents[1] / "scripts" / "resolve_rapx.py"
RESOLVER_SPEC = importlib.util.spec_from_file_location("resolve_rapx", RESOLVER)
resolve_rapx = importlib.util.module_from_spec(RESOLVER_SPEC)
RESOLVER_SPEC.loader.exec_module(resolve_rapx)


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

    def test_release_time_nightly_is_pinned(self):
        data = {
            "crate": {"max_stable_version": "0.7.50"},
            "versions": [
                {"num": "0.7.50", "yanked": False, "created_at": "2026-09-19T02:00:00Z"},
            ],
        }
        self.assertEqual(
            resolve_rapx.release_metadata(data),
            {
                "version": "0.7.50",
                "published_at": "2026-09-19T02:00:00Z",
                "toolchain": "nightly-2026-09-18",
            },
        )


if __name__ == "__main__":
    unittest.main()
