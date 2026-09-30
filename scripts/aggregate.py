#!/usr/bin/env python3
"""Combine per-crate results into a minimal Markdown and JSON summary."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


KEYS = ("SOUND", "UNSOUND", "UNKNOWN", "NOT_RUN")


def rate(value: int, total: int) -> float:
    return round(value * 100.0 / total, 2) if total else 0.0


def cell(value: int, total: int) -> str:
    return f"{value} ({rate(value, total):.2f}%)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rapx-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    order = {item["name"]: index for index, item in enumerate(manifest["crates"])}
    results = [json.loads(path.read_text()) for path in args.input.rglob("result.json")]
    results.sort(key=lambda item: order.get(item["crate"], len(order)))

    counts = {key: sum(row["counts"][key] for row in results) for key in KEYS}
    total = sum(row["active_targets"] for row in results)
    output = {
        "rapx_version": args.rapx_version,
        "crate_count": len(results),
        "active_targets": total,
        "counts": counts,
        "percentages": {key: rate(counts[key], total) for key in KEYS},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "crates": results,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(output, indent=2) + "\n")

    lines = [
        f"# RAPx {args.rapx_version} targeted results",
        "",
        f"**Soundness pass rate: {counts['SOUND']} / {total} = {rate(counts['SOUND'], total):.2f}%**",
        "",
        "| Result | Count | Rate |",
        "|---|---:|---:|",
    ]
    lines.extend(f"| {key} | {counts[key]} | {rate(counts[key], total):.2f}% |" for key in KEYS)
    lines.extend([
        "",
        "| Crate | Targets | SOUND | UNSOUND | UNKNOWN | NOT_RUN |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in results:
        row_total = row["active_targets"]
        lines.append(
            f"| `{row['crate']} {row['crate_version']}` | {row_total} | "
            + " | ".join(cell(row["counts"][key], row_total) for key in KEYS)
            + " |"
        )
    (args.output / "summary.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
