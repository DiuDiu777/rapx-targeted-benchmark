# RAPx targeted benchmark

This repository contains the 10 crates with the most public targets in the
2026-09-28 175-crate RAPx run. Their published source is pinned and each target
is annotated with `#[rapx::verify]`.

The **Targeted RAPx verify** workflow has only `workflow_dispatch`; run it from
the Actions page whenever a measurement is needed. The form has separate
timeouts for ordinary crates and `smallvec`; their defaults are 15 and 120
minutes respectively. Every run resolves and installs the newest non-yanked
`rapx` release from crates.io, then runs:

```text
cargo +nightly rapx verify --mode targeted --postfix-repeat auto
```

Ten crates run independently. The workflow summary and `targeted-summary`
artifact contain only the latest RAPx version, its release-time nightly, and
`SOUND`, `UNSOUND`, `UNKNOWN`, and `NOT_RUN` counts and percentages. The pass
rate is `SOUND / targets listed in targets.json`.

`NOT_RUN` means that RAPx emitted no verdict for that manifest target. Typical
causes are a disabled Cargo feature or platform `cfg`, a per-crate timeout, or
RAPx stopping or omitting a target before producing its result. It is not an
`UNSOUND` verdict. rustc may print an internal type behind a public type alias;
the result parser maps known aliases before deciding that a target did not run.
RAPx 0.7.50 also selects some unannotated `Drop` implementations in targeted
mode, so records not present in `targets.json` are excluded from the benchmark.

RAPx uses unstable rustc-private APIs, so a floating `nightly` can stop compiling
after a rustc change. The resolver pins the nightly available when the selected
RAPx release was published; the setup job installs RAPx and runs a CLI self-check
before starting the 10 verification jobs.

`targets.json` records the selected API paths, crate versions, original crate
archive checksums, and historical download ranks. Some API paths have more than
one source annotation behind mutually exclusive `cfg` branches; they still
count as one manifest target.

## Results

The repository's `results/` directory is intentionally ignored because a
GitHub-hosted runner has an ephemeral filesystem. Results are attached to each
workflow run instead:

- `targeted-summary` contains `summary.md` and `summary.json` and is retained
  for 90 days.
- Each `result-<crate>-<version>` artifact contains that crate's `result.json`
  and full `rapx.log` and is retained for 30 days.

Open a completed workflow run and download these files from the **Artifacts**
section at the bottom of its Summary page. The compact table is also rendered
directly in the run's job summary.
