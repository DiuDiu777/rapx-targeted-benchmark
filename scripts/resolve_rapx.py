#!/usr/bin/env python3
"""Resolve the newest non-yanked RAPx release and its release-time nightly."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


URL = "https://crates.io/api/v1/crates/rapx"


def release_metadata(data: dict) -> dict:
    releases = [version for version in data["versions"] if not version["yanked"]]
    if not releases:
        raise ValueError("crates.io returned no non-yanked RAPx release")
    # The crates.io API returns versions newest first. max_stable_version is
    # preferred when present so a pre-release does not silently replace it.
    version = data["crate"].get("max_stable_version") or releases[0]["num"]
    release = next((item for item in releases if item["num"] == version), None)
    if release is None:
        raise ValueError(f"crates.io returned an invalid RAPx version: {version}")
    published = datetime.fromisoformat(release["created_at"].replace("Z", "+00:00"))
    # Pinning the nightly available immediately before the release prevents
    # later rustc_private API changes from breaking cargo install. For example,
    # RAPx 0.7.50 was published on 2026-09-19 and its official docs.rs build
    # used nightly-2026-09-18.
    toolchain = "nightly-" + (published.date() - timedelta(days=1)).isoformat()
    return {
        "version": version,
        "published_at": release["created_at"],
        "toolchain": toolchain,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    response = subprocess.run(
        [
            "curl", "--fail", "--location", "--silent", "--show-error",
            "--retry", "3", "--max-time", "30",
            "--user-agent", "rapx-targeted-benchmark/1.0", URL,
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    data = json.loads(response.stdout)
    metadata = release_metadata(data)
    if args.github_output:
        with args.github_output.open("a") as output:
            for key, value in metadata.items():
                output.write(f"{key}={value}\n")
    else:
        print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"failed to resolve RAPx: {error}", file=sys.stderr)
        raise SystemExit(1)
