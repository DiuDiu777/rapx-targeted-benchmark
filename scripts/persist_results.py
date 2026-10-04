#!/usr/bin/env python3
"""Store a compact workflow result under a dated repository directory."""

import argparse
import json
import shutil
from pathlib import Path


def rebuild_index(results_root: Path) -> None:
    runs = []
    for metadata_path in results_root.glob("*/run-*/run.json"):
        metadata = json.loads(metadata_path.read_text())
        run_dir = metadata_path.parent
        runs.append((metadata, run_dir.relative_to(results_root)))
    runs.sort(
        key=lambda item: (
            item[0]["run_date"],
            int(item[0]["run_id"]),
            int(item[0].get("run_attempt", 1)),
        ),
        reverse=True,
    )

    lines = [
        "# Benchmark results",
        "",
        "Results are grouped by run date in Asia/Shanghai time.",
        "",
        "| Date | Run | Commit | RAPx | Summary |",
        "|---|---:|---|---|---|",
    ]
    for metadata, run_dir in runs:
        sha = metadata["commit_sha"]
        run_label = metadata["run_id"]
        run_attempt = int(metadata.get("run_attempt", 1))
        if run_attempt > 1:
            run_label += f" (attempt {run_attempt})"
        lines.append(
            f"| {metadata['run_date']} | "
            f"[{run_label}]({metadata['run_url']}) | "
            f"`{sha[:7]}` | `{metadata['rapx_version']}` | "
            f"[results]({run_dir.as_posix()}/summary.md) |"
        )
    (results_root / "README.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", type=int, default=1)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--commit-sha", required=True)
    args = parser.parse_args()

    summary = json.loads((args.summary / "summary.json").read_text())
    run_name = f"run-{args.run_id}"
    if args.run_attempt > 1:
        run_name += f"-attempt-{args.run_attempt}"
    run_dir = args.results_root / args.run_date / run_name
    crates_dir = run_dir / "crates"
    crates_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.summary / "summary.md", run_dir / "summary.md")
    shutil.copy2(args.summary / "summary.json", run_dir / "summary.json")

    result_paths = sorted(args.input.rglob("result.json"))
    if len(result_paths) != summary["crate_count"]:
        raise RuntimeError(
            f"expected {summary['crate_count']} crate results, found {len(result_paths)}"
        )
    for path in result_paths:
        result = json.loads(path.read_text())
        name = f"{result['crate']}-{result['crate_version']}.json"
        shutil.copy2(path, crates_dir / name)

    metadata = {
        "run_date": args.run_date,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "run_url": args.run_url,
        "commit_sha": args.commit_sha,
        "rapx_version": summary["rapx_version"],
        "toolchain": summary["toolchain"],
        "crate_count": summary["crate_count"],
        "target_count": summary["active_targets"],
    }
    (run_dir / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    rebuild_index(args.results_root)
    print(run_dir)


if __name__ == "__main__":
    main()
