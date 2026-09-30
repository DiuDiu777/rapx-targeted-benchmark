#!/usr/bin/env python3
"""Run one targeted RAPx verification and emit compact result counts."""

import argparse
import json
import os
import re
import signal
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
HEADER = re.compile(r"\[rapx::verify\]\s*(?:function:|sequence:|unsafe impl)\s*(.+)")
RESULT = re.compile(r"\b(?:result|verdict):\s*(SOUND|UNSOUND|UNKNOWN|SAFE|UNSAFE)\b")
VERDICT_PRIORITY = {"SOUND": 0, "UNKNOWN": 1, "UNSOUND": 2}


def _without_generics(path: str) -> str:
    """Remove Rust generic arguments while preserving a callable's path."""
    output = []
    depth = 0
    for char in path:
        if char == "<":
            if depth == 0 and len(output) >= 2 and output[-2:] == [":", ":"]:
                del output[-2:]
            depth += 1
        elif char == ">" and depth:
            depth -= 1
        elif depth == 0:
            output.append(char)
    return "".join(output)


def canonical_target(label: str, crate_name: str) -> str:
    """Normalize RAPx/rustc labels to the API paths stored in targets.json."""
    label = label.strip()

    # rustc prints trait methods as `<Type as Trait>::method`.
    trait_method = re.match(r"^<(.+?)\s+as\s+.+>::([^:]+)$", label)
    if trait_method:
        label = f"{trait_method.group(1)}::{trait_method.group(2)}"
    else:
        # Some generated impl modules use `::<impl Trait for Type>::method`.
        impl_method = re.match(r"^.*?::<impl\s+.+\s+for\s+(.+)>::([^:]+)$", label)
        if impl_method:
            label = f"{impl_method.group(1)}::{impl_method.group(2)}"

    label = _without_generics(label)
    label = re.sub(r"\s+", "", label)
    for crate_prefix in (crate_name, crate_name.replace("-", "_")):
        prefix = crate_prefix + "::"
        if label.startswith(prefix):
            label = label[len(prefix):]
            break
    return label


def parse_log(text: str, intended_targets: list[str], crate_name: str) -> dict:
    clean = ANSI.sub("", text)
    records = []
    current = None
    for line in clean.splitlines():
        header = HEADER.search(line)
        if header:
            if current is not None:
                records.append((current, "UNKNOWN"))
            current = header.group(1).strip()
            continue
        result = RESULT.search(line)
        if result and current is not None:
            verdict = {"SAFE": "SOUND", "UNSAFE": "UNSOUND"}.get(
                result.group(1), result.group(1)
            )
            records.append((current, verdict))
            current = None
    if current is not None:
        records.append((current, "UNKNOWN"))

    intended = {
        canonical_target(target, crate_name): target for target in intended_targets
    }
    matched = {}
    ignored = []
    for label, verdict in records:
        normalized = canonical_target(label, crate_name)
        if normalized not in intended:
            ignored.append(label)
            continue
        previous = matched.get(normalized)
        if previous is None or VERDICT_PRIORITY[verdict] > VERDICT_PRIORITY[previous]:
            matched[normalized] = verdict

    counts = Counter(matched.values())
    counts["NOT_RUN"] = len(intended) - len(matched)
    return {
        "active_targets": len(intended),
        "observed_targets": len(matched),
        "observed_log_records": len(records),
        "ignored_log_records": len(ignored),
        "ignored_log_targets": ignored,
        "counts": {key: counts[key] for key in ("SOUND", "UNSOUND", "UNKNOWN", "NOT_RUN")},
    }


def percentages(counts: dict, total: int) -> dict:
    if total == 0:
        return {key: 0.0 for key in counts}
    return {key: round(value * 100.0 / total, 2) for key, value in counts.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crate", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--declared-targets", required=True, type=int)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rapx-version", required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--timeout-minutes", type=int, default=330)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    crate_dir = Path(args.crate).resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    log_path = args.output / "rapx.log"
    command = [
        "cargo", "+" + args.toolchain, "rapx", "verify",
        "--mode", "targeted", "--postfix-repeat", "auto",
        "--crate", args.name,
        "--", "--locked", "--jobs", "1",
    ]
    env = dict(os.environ)
    for key in ("RUSTFLAGS", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "CARGO_ENCODED_RUSTFLAGS"):
        env.pop(key, None)
    env.update({
        "CARGO_BUILD_JOBS": "1",
        "CARGO_INCREMENTAL": "0",
        "CARGO_TARGET_DIR": str(args.output / "target"),
        "CARGO_TERM_COLOR": "never",
        "NUM_JOBS": "1",
        "RAYON_NUM_THREADS": "1",
        "RAPX_CLEAN": "false",
        "RAPX_RECURSIVE": "none",
        "RUST_BACKTRACE": "1",
    })

    started = time.monotonic()
    timed_out = False
    with log_path.open("w") as log:
        log.write("command: " + json.dumps(command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=crate_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            exit_code = process.wait(timeout=args.timeout_minutes * 60)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            exit_code = process.returncode

    manifest = json.loads(args.manifest.read_text())
    crate_manifest = next(
        item
        for item in manifest["crates"]
        if item["name"] == args.name and item["version"] == args.version
    )
    intended_targets = [item["api"] for item in crate_manifest["targets"]]
    if len(intended_targets) != args.declared_targets:
        raise ValueError(
            f"manifest count mismatch for {args.name}: "
            f"{len(intended_targets)} != {args.declared_targets}"
        )
    parsed = parse_log(
        log_path.read_text(errors="replace"), intended_targets, args.name
    )
    counts = parsed["counts"]
    total = parsed["active_targets"]
    if timed_out:
        status = "TIMEOUT"
    elif exit_code != 0:
        status = "PARTIAL" if parsed["observed_targets"] else "FAILED"
    elif counts["NOT_RUN"]:
        status = "PARTIAL"
    else:
        status = "COMPLETE"
    result = {
        "crate": args.name,
        "crate_version": args.version,
        "rapx_version": args.rapx_version,
        "toolchain": args.toolchain,
        "status": status,
        "declared_api_targets": args.declared_targets,
        "active_targets": total,
        "counts": counts,
        "percentages": percentages(counts, total),
        "observed_log_records": parsed["observed_log_records"],
        "ignored_log_records": parsed["ignored_log_records"],
        "ignored_log_targets": parsed["ignored_log_targets"],
        "exit_code": exit_code,
        "timed_out": timed_out,
        "seconds": round(time.monotonic() - started, 2),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
