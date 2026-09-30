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
    def test_counts_only_manifest_targets_and_aggregates_overloads(self):
        log = """
        00|RAPx|INFO|: [rapx::verify] function: api::one
        00|RAPx|INFO|: result: SOUND
        00|RAPx|INFO|: [rapx::verify] function: <api::Thing<T> as Trait>::two
        00|RAPx|INFO|: result: SOUND
        00|RAPx|INFO|: [rapx::verify] function: <api::Thing<T> as OtherTrait>::two
        00|RAPx|WARN|: result: UNSOUND
        00|RAPx|INFO|: [rapx::verify] function: internal::Unmarked::drop
        00|RAPx|INFO|: result: SOUND
        """
        result = run_one.parse_log(
            log,
            ["demo::api::one", "demo::api::Thing::two", "demo::api::three"],
            "demo",
        )
        self.assertEqual(result["active_targets"], 3)
        self.assertEqual(result["observed_targets"], 2)
        self.assertEqual(result["observed_log_records"], 4)
        self.assertEqual(result["ignored_log_records"], 1)
        self.assertEqual(
            result["counts"],
            {"SOUND": 1, "UNSOUND": 1, "UNKNOWN": 0, "NOT_RUN": 1},
        )

    def test_normalizes_generated_impl_and_turbofish(self):
        self.assertEqual(
            run_one.canonical_target(
                "boxed::ops::<impl std::ops::Drop for boxed::BitBox<T, O>>::drop",
                "bitvec",
            ),
            "boxed::BitBox::drop",
        )
        self.assertEqual(
            run_one.canonical_target(
                "rkyv::place::Place::<T: MetaSized>::write_unchecked", "rkyv"
            ),
            "place::Place::write_unchecked",
        )
        self.assertEqual(
            run_one.canonical_target(
                "allocator_api2::boxed::Box::<T>::from_raw", "allocator-api2"
            ),
            "boxed::Box::from_raw",
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
