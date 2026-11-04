# flmint: Claude Code project instructions

`AGENTS.md` is the canonical rules file. Read `HANDOFF.md` for the detailed operating policy and history. Read
`docs/plan.md` for the forward plan, `docs/rollback.md` for snapshot guarantees, `docs/architecture.md` for module
boundaries, and `reports/` for evidence. Keep this file and `AGENTS.md` in sync; if they disagree, `AGENTS.md` wins
and drift should be fixed in the same change. If `HANDOFF.md` is missing, ask the operator to copy
`FLSTUDIO_LINUX_OPENCODE_HANDOFF.md` into the repository before host-changing work.

## Operating boundaries

- The workstation is production hardware. Do not perform unapproved `sudo`, OS migration, system package,
  driver, kernel, PipeWire config, Windows installer, third-party download, activation, build, benchmark,
  plugin, recording, or export actions. Host-changing work needs explicit owner approval, a pinned version or
  digest, and a fresh pre-mutation snapshot.
- `flmint` must not run `sudo` or `apt`. Host-package prerequisites are recorded and requested, not executed.
- Confine writes to `~/.local/share/flmint`, `~/.local/state/flmint`, `~/.local/opt/flmint`, and repo-relative
  paths accepted by `safe_relative_path`. Never touch `~/.wine`, system Wine, or another tool's prefix or data
  directory.
- Prefix snapshots cover only `~/.local/share/flmint/profiles/<profile>/prefix`. They do not roll back runner
  binaries, `~/.local/lib/wine` PipeASIO files, PipeASIO config, system packages, PipeWire state, or installer
  files.
- Preserve `prefix.discarded-*` until the owner confirms cleanup. Preserve logs and reports.
- Use at most 2 concurrent subagents and at most 1 heavy compilation at a time. Never start unbounded builds or
  AI benchmarks.
- Status labels are `verified`, `partial`, `unverified`, `not tested`, or `blocked`. Never claim FL Studio, VST,
  audio latency, GPU, activation, save/reopen, export, recording, or license behavior without captured evidence.

## Verification commands

Set up the project virtual environment when missing:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Run all gates for every meaningful change:

```bash
bash scripts/smoke_test.sh
```

`scripts/smoke_test.sh` runs:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/mypy
```

Focused test example:

```bash
.venv/bin/python -m pytest tests/test_cli.py::CliTest::test_install_without_dry_run_refuses
```

Last recorded gates: `93 passed, 18 subtests passed`, `All checks passed!`,
`Success: no issues found in 18 source files`.

## Repository commands

Read-only or managed-state commands:

```bash
bash scripts/collect_host_facts.sh
.venv/bin/python -m flmint doctor --format text
.venv/bin/python -m flmint doctor --format json --save reports/host-audit.json
.venv/bin/python -m flmint doctor --compare reports/host-audit-2026-11-03-post-d5.json
.venv/bin/python -m flmint plan --profile stable
.venv/bin/python -m flmint install --installer PATH --profile stable --dry-run
.venv/bin/python -m flmint snapshot list --profile stable
```

Approval-gated managed-artifact commands, run only after explicit owner approval and when a fresh pre-action
snapshot exists:

```bash
.venv/bin/python -m flmint fetch --profile stable --component daw-ge-proton --approve --extract
.venv/bin/python -m flmint verify --profile stable --component daw-ge-proton
.venv/bin/python -m flmint snapshot create --profile stable --name SNAPSHOT_NAME
.venv/bin/python -m flmint snapshot restore --profile stable --name SNAPSHOT_NAME
```

Expected refusal boundaries:

- `install` without `--dry-run` exits `2` with `ApprovalRequiredError`.
- `launch`, `diagnose`, and `bench` exit `2` with `NotYetImplementedError`.
- `fetch` requires `--approve`.
- `snapshot create` refuses until a prefix exists.
- `snapshot restore` verifies the archive SHA-256, extracts only a single `prefix` tree into staging, and
  preserves the replaced prefix as `prefix.discarded-*`.

## Code map and testing notes

- CLI entry point: `src/flmint/cli.py`.
- Profile loading and pin validation: `src/flmint/manifest.py`, `profiles/stable.yaml`, and example profiles.
- Side-effect boundary: `src/flmint/installer_runner.py`; `perform_install()` is an intentional refusal.
- Snapshot implementation: `src/flmint/snapshots.py`.
- Managed-path and safe-write helpers: `src/flmint/state.py`.
- Host probes use bounded argv subprocess calls, no shell, and record absent tools as facts.
- Tests use `tests/helpers.py` fake probers and fixtures; `FLMINT_OS_RELEASE` is the test-only os-release hook.
- Python requirement is `>=3.12`. Use stdlib-first, typed code; do not add new dependencies without asking first.
- `mypy` checks `src/flmint`; `ruff` checks `src` and `tests`.

## Host facts that matter now

- Stable uses pinned DAW-GE-Proton, not Bottles. Runner root is
  `~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c/DAW-GE-Proton11-6c`, with bundled Wine reported as
  `wine-11.0 (Staging)`.
- Stable prefix: `~/.local/share/flmint/profiles/stable/prefix`.
- Experimental prefix: `~/.local/share/flmint/profiles/experimental/prefix`.
- PipeASIO v1.10.0 is installed under `~/.local/lib/wine` and registered in the experimental prefix.
- PipeASIO launch requires `WINEDLLPATH=$HOME/.local/lib/wine` and `XDG_RUNTIME_DIR=/run/user/1000`. Missing the
  runtime directory fails with `pw_context_connect failed`. Working launches did not need `PIPEWIRE_REMOTE` or
  `PULSE_SERVER`.
- Accepted experimental PipeASIO setting is 256 fixed samples: `buffer_size=256`, `fixed_buffer_size=on`, and
  `sample_rate=0` in `~/.config/pipeasio/config.ini`.
- Final accepted PipeASIO launch and clean-stop commands are stored in `reports/pipeasio-experimental.md`. Use a
  supervised manual launch only after approval and a fresh pre-test snapshot; `flmint launch` is still a stub.
- Check `flmint snapshot list --profile experimental` before prefix mutation. The **golden** experimental snapshot is
  `golden-2026-11-05` (read-only hard link of `pre-reopen-test-2026-11-04`, sha256 `f8d0ef47...86b5b`): the last
  state proven by a successful run (FLEX loads, path-launch save/reopen verified). It includes the XRandR-key
  removal, vkd3d DLLs in `system32`/`syswow64`, `Fonts/Verdana.ttf` (DejaVu Sans substitute), and 18 absolute runner
  font symlinks. Never delete or overwrite it. See `reports/gui-plugin-asio-diagnosis-2026-11-04.md`.
- Never set winex11 `UseXRandR`/`UseXVidMode` to `N` on this host: it crashed Xorg (NVIDIA, rotated + scaled monitors).
- File > Open / Save As hang FL behind an off-screen dialog (Wine `itemdlg.c` custom-control bug). Open projects by
  launching with the `.flp` path (`Z:\...`) or from recent files, and save with Ctrl+S to an existing path. Recover a
  stuck session with the runner `wineserver -k`.
- `D4` is no longer a decision blocker, but activation, WAV export, latency benchmarking, third-party plugins,
  recording/monitoring, and round-trip latency remain untested. Save/reopen is `verified` only for the
  path-launch + Ctrl+S workflow (2026-11-05).
