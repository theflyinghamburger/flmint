# flmint

Non-destructive planning and verification toolkit for running FL Studio on Linux through isolated
Wine/Proton prefixes and pinned compatibility runtimes. It plans, verifies, and makes prefix changes
reversible. It does not install FL Studio, Wine, or any audio bridge.

## What works today (executed and verified on this host)

- `flmint doctor` — read-only host inventory (`text` and `json`), non-root, no mutation, graceful
  handling of absent tools. Audit saved to `reports/host-audit.json`. `doctor --compare` compares current
  facts with a saved audit JSON and exits `1` on material host/capability/blocker drift.
- Installer validation — streaming SHA-256, PE header parse, **NSIS installer-stub detection**
  (`installer_engine: nsis`), no execution.
- `flmint plan` — deterministic, side-effect-free plan from a profile: gates (PipeWire ≥ 1.4.2),
  ordered steps flagged `[auto]` / `[approval]` / `[BLOCKED]`, blockers, warnings, next actions.
- `flmint install --dry-run` — the same plan rendered as an install preview, `(no mutations performed)`.
- `flmint snapshot list` — reports managed snapshots without creating state. The live stable profile has
  `baseline`, pre-installer, and post-install snapshots.
- `flmint fetch --profile stable --component daw-ge-proton --approve [--extract]` — digest-gated fetch of a
  profile-pinned artifact into `~/.local/opt/flmint/<component>/`: pinned `size_bytes` + SHA-256 enforced
  while streaming, a digest mismatch quarantines the file and extracts nothing, `tarfile` `filter="data"`
  extraction, and a provenance record with the signed CDN redirect query stripped. Refuses without
  `--approve` (exit 2).
- `flmint verify --profile ... --component ...` — re-hashes an already stored artifact with no network and
  rewrites its provenance record.
- Unit tests, `ruff`, `mypy`: `93 passed, 18 subtests passed` / `All checks passed!` /
  `Success: no issues found in 18 source files`.

## Implemented but not yet exercised on real hardware

- `flmint snapshot create` / `restore` — archive + SHA-256 verification, staging extraction, preserved
  `prefix.discarded-*` rollback, disk headroom checks. Unit-tested and exercised against the managed Wine prefix
  during the 2.4 retry path.
- `flmint install` **without** `--dry-run` — always refuses with `ApprovalRequiredError` (exit 2). This
  is the Phase 2 boundary, not a missing feature.
- `flmint snapshot restore` against a real Wine prefix (staging + swap + `prefix.discarded-*` rollback): the
  prefix exists, multiple restore round-trips were exercised during 2.4, and rollback copies remain pending
  operator deletion. `flmint launch`, `diagnose`, `bench` and `install` without `--dry-run` still refuse.
  Full evidence: `reports/runner-install-phase2.md`.
- Phase stubs — `launch`, `diagnose`, `bench audio`, `bench ai` raise `NotYetImplementedError`.

## Requires human approval before it can happen

- Any download, `flatpak --user install`, runner extraction, or build (Wine/Proton, PipeASIO, WineASIO).
  Executed so far under approvals (2026-11-03): pinned `DAW-GE-Proton11-6c` fetch + extraction, managed
  prefix creation, and a digest-matched PipeASIO v1.10.0 install/register in an experimental prefix. No Flatpak
  install or WineASIO installation has run.
- A host 32-bit loader decision (**D5**, answered 2026-11-03 = option (a)): the multilib runner cannot
  bootstrap a prefix without `/lib/ld-linux.so.2`. The owner ran `sudo apt install libc6-i386` personally
  (`libc6-i386 2.44-1ubuntu2`); `flmint` never runs `sudo` or `apt`. That is the only system package change.
- The supervised FL Studio installer run (2.4): approved and completed as a silent `/S` install; interactive
  installer UI behavior remains unverified.
- License activation, full `FL64.exe` save/reopen, WAV export, formal PipeASIO latency benchmarking,
  JACK/realtime changes, and plugins remain unapproved or untested. A supervised launch/manual-auth attempt,
  PipeASIO install/register, and supervised PipeASIO launch tests at 512 and 256 samples have been approved and
  executed. The accepted PipeASIO setting is 256 fixed samples, with one logged XRUN warning and no user-reported
  glitches. D4 is no longer a decision blocker, but activation/save/reopen/export still must be actually tested
  before they can be claimed as verified.
- Pinning exact versions + SHA-256 into profiles.
- Installing JACK / realtime scheduling changes for the WineASIO fallback.
- FL Studio behavior validation: full activation, save/reopen, WAV export, formal latency/XRUN benchmarking,
  plugin compatibility, GPU behavior, AI coexistence. These remain **not verified on this host**, though PipeASIO
  launch/select/audio startup has now been observed at 512 and 256 samples.

## Quick commands

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/python -m flmint doctor --format text
.venv/bin/python -m flmint doctor --format json --save reports/host-audit.json
.venv/bin/python -m flmint doctor --compare reports/host-audit-2026-11-03-post-d5.json
.venv/bin/python -m flmint plan --installer "$HOME/Downloads/flstudio_win64_26.1.7.5654.exe" --profile stable
.venv/bin/python -m flmint install --installer "$HOME/Downloads/flstudio_win64_26.1.7.5654.exe" --profile stable --dry-run
.venv/bin/python -m flmint snapshot list --profile stable
.venv/bin/python -m flmint fetch --profile stable --component daw-ge-proton          # refuses (no --approve)
.venv/bin/python -m flmint verify --profile stable --component daw-ge-proton        # re-hash + provenance

.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/mypy
```

`install` without `--dry-run`, `launch`, `diagnose`, and `bench` intentionally exit `2` with a message
and `next action:` hints.

## Docs

- `HANDOFF.md` — operating policy (section 10) and phase gates (section 8); `AGENTS.md` points here.
- `docs/plan.md` — forward execution plan: blocking decisions D1-D4, Phase 2-6 task order, safe backlog.
- `CLAUDE.md` — same project rules for Claude Code (kept in sync with `AGENTS.md`).
- `docs/architecture.md` — modules, control flow, safety invariants.
- `docs/rollback.md` — snapshot contract, guarantees, and known limits.
- `docs/runbook.md` — safe commands, exit-code expectations, Phase 2 preflight checklist.
- `docs/upstream-research.md` — verified/unverified upstream findings.
- `docs/os-migration-decision.md` — distro decision from measured host facts.
- `docs/compatibility-matrix.md` — host gates (measured) and FL Studio rows (all `not tested`).
- `docs/benchmarks.md` — measurement plan and claims that are currently forbidden.

## Status caveat

FL Studio full activation, save/reopen, export, formal audio latency, plugin behavior, and GPU behavior are
**not verified** on this host. PipeASIO launch/select/audio startup has been observed at 512 and 256 samples,
with 256 accepted for this session. A documented Windows fallback remains part of the plan.
