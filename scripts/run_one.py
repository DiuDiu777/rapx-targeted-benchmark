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
TOTAL = re.compile(
    r"\[rapx::verify\]\s*total:\s*(\d+)\s+free function\(s\),\s*"
    r"(\d+)\s+method\(s\)"
)


def parse_log(text: str, declared_targets: int) -> dict:
    clean = ANSI.sub("", text)
    records = []
    current = None
    active_targets = None
    for line in clean.splitlines():
        total = TOTAL.search(line)
        if total:
            active_targets = int(total.group(1)) + int(total.group(2))
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

    counts = Counter(verdict for _, verdict in records)
    denominator = active_targets if active_targets is not None else declared_targets
    denominator = max(denominator, len(records))
    counts["NOT_RUN"] = max(0, denominator - len(records))
    return {
        "active_targets": denominator,
        "observed_targets": len(records),
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
    parser.add_argument("--rapx-version", required=True)
    parser.add_argument("--timeout-minutes", type=int, default=330)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    crate_dir = Path(args.crate).resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    log_path = args.output / "rapx.log"
    command = [
        "cargo", "+nightly", "rapx", "verify",
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

    parsed = parse_log(log_path.read_text(errors="replace"), args.declared_targets)
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
        "status": status,
        "declared_api_targets": args.declared_targets,
        "active_targets": total,
        "counts": counts,
        "percentages": percentages(counts, total),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "seconds": round(time.monotonic() - started, 2),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
