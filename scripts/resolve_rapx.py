#!/usr/bin/env python3
"""Resolve the newest non-yanked RAPx release from crates.io."""

import json
import subprocess
import sys


URL = "https://crates.io/api/v1/crates/rapx"


def main() -> None:
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
    releases = [version for version in data["versions"] if not version["yanked"]]
    if not releases:
        raise SystemExit("crates.io returned no non-yanked RAPx release")
    # The crates.io API returns versions newest first. max_stable_version is
    # preferred when present so a pre-release does not silently replace it.
    version = data["crate"].get("max_stable_version") or releases[0]["num"]
    if version not in {release["num"] for release in releases}:
        raise SystemExit(f"crates.io returned an invalid RAPx version: {version}")
    print(version)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"failed to resolve RAPx: {error}", file=sys.stderr)
        raise SystemExit(1)
