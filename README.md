# RAPx targeted benchmark

This repository contains the 10 crates with the most public targets in the
2026-09-28 175-crate RAPx run. Their published source is pinned and each target
is annotated with `#[rapx::verify]`.

The **Targeted RAPx verify** workflow has only `workflow_dispatch`; run it from
the Actions page whenever a measurement is needed. Every run resolves and
installs the newest non-yanked `rapx` release from crates.io, then runs:

```text
cargo +nightly rapx verify --mode targeted --postfix-repeat auto
```

Ten crates run independently. The workflow summary and `targeted-summary`
artifact contain only the latest RAPx version, its release-time nightly, and
`SOUND`, `UNSOUND`, `UNKNOWN`, and `NOT_RUN` counts and percentages. The pass
rate is `SOUND / active targets`.

RAPx uses unstable rustc-private APIs, so a floating `nightly` can stop compiling
after a rustc change. The resolver pins the nightly available when the selected
RAPx release was published; the setup job installs RAPx and runs a CLI self-check
before starting the 10 verification jobs.

`targets.json` records the selected API paths, crate versions, original crate
archive checksums, and historical download ranks. Some API paths have more than
one source annotation behind mutually exclusive `cfg` branches; RAPx's active
target count is therefore taken from the current run before percentages are
calculated.
