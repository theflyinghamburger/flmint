# flmint

Run FL Studio (a Windows music app) on Linux without risking the computer it runs on.

## The idea, explained simply

FL Studio is built for Windows. Linux can run Windows programs through **Wine**, a translator that turns
Windows requests into Linux ones. Wine is not perfect, though. Some versions break things, some settings
crash the whole screen, and one bad change can leave a setup you can't fix.

`flmint` is a careful helper that sets FL Studio up on Linux and keeps it safe. Think of it like this:

- **A sandbox for each setup.** FL Studio lives in its own box (a Wine *prefix*) under
  `~/.local/share/flmint/profiles/<profile>/prefix`. Nothing else on the computer is touched: not `~/.wine`,
  not system Wine, and not other apps.
- **The same translator every time.** The Wine build (the *runner*, DAW-GE-Proton) is pinned to one exact
  version and checked against a fingerprint (SHA-256) before use. No surprise upgrades.
- **Photos before every change.** Before changing the box, `flmint` takes a *snapshot* (a compressed
  copy). If something breaks, restore the photo. One snapshot is marked **golden**: the last state that was
  proven to work.
- **Ask before doing anything big.** Downloading, installing or launching needs an explicit `--approve`.
  `flmint` never runs `sudo` or `apt`. Anything that needs system changes is written down for a human to do.
- **Only believe what was tested.** Every claim is labelled `verified`, `partial`, `unverified`,
  `not tested` or `blocked`, and backed by evidence in `reports/`.

## How it works (methodology)

1. **Look first.** `flmint doctor` inventories the machine (OS, GPU, PipeWire, Wine, disk) without changing
   anything, and can compare against an earlier audit to spot drift.
2. **Plan without doing.** `flmint plan` reads a *profile* (a YAML recipe in `profiles/`) and prints the
   ordered steps, gates (for example PipeWire ≥ 1.4.2) and blockers. Nothing runs.
3. **Fetch only what is pinned.** `flmint fetch --approve` downloads one profile-pinned file. The size and
   SHA-256 are checked while it downloads. A mismatch is quarantined and never unpacked.
4. **Snapshot, change, test, record.** Each change to a prefix follows the same loop: take a snapshot, make
   one change, run a supervised test, and write the result into `reports/`. If the test fails, restore the
   snapshot.
5. **Launch cleanly.** `flmint launch` builds FL Studio's environment from scratch, so stray variables from
   your shell can't leak in. It also refuses known hazards before anything starts.

## Project layout

```text
src/flmint/          the tool
  cli.py             command-line entry point (all commands below)
  doctor.py, probe.py read-only host inventory
  manifest.py        loads and validates profiles (pins, gates)
  planner.py         side-effect-free plans
  downloads.py       pinned, digest-checked fetch/verify
  snapshots.py       create/list/restore prefix snapshots
  runtime_launcher.py launch/stop FL Studio with a clean environment
  projects.py        new FL projects from templates
  state.py           safe managed-path writes
profiles/            recipes: stable.yaml, experimental.yaml (+ *.example.yaml)
tests/               unit tests (fake hosts, no real side effects)
scripts/             smoke_test.sh (all gates), collect_host_facts.sh
docs/                plan, architecture, rollback, runbook, research
reports/             evidence from real runs (gitignored)
```

Everything `flmint` writes goes to three places in your home directory:

| Path | Holds |
| --- | --- |
| `~/.local/share/flmint` | prefixes, snapshots, projects |
| `~/.local/state/flmint` | logs, PID files |
| `~/.local/opt/flmint` | pinned runners and downloads |

## Profiles

| Profile | What it is |
| --- | --- |
| `stable` | FL Studio on the pinned DAW-GE-Proton runner |
| `experimental` | Same runner plus **PipeASIO** (low-latency audio through PipeWire, 256 fixed samples). This is the one in daily use. |

## Usage

Setup (Python ≥ 3.12):

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
alias flmint='.venv/bin/python -m flmint'
```

Look and plan (safe and read-only):

```bash
flmint doctor --format text
flmint plan --profile stable
flmint snapshot list --profile experimental
```

Make music (the everyday workflow):

```bash
flmint new-project my-song                      # copies a template to ~/.local/share/flmint/projects/my-song.flp
flmint new-project --list-templates             # pick another with --template Category/Name

flmint launch --profile experimental --project ~/.local/share/flmint/projects/my-song.flp --dry-run
flmint launch --profile experimental --project ~/.local/share/flmint/projects/my-song.flp \
  --approve --snapshot before-my-song           # or --no-snapshot

flmint stop --profile experimental              # close everything in the prefix (also unsticks a hang)
```

Inside FL Studio, **save with Ctrl+S**. Don't use File > Open or File > Save As. Under this runner those
dialogs open off-screen and freeze FL (a Wine bug). To open a project, launch with `--project`, or use
FL's recent-files list.

Safety and maintenance:

```bash
flmint snapshot create  --profile experimental --name NAME
flmint snapshot restore --profile experimental --name NAME   # keeps the old prefix as prefix.discarded-*
flmint fetch  --profile stable --component daw-ge-proton --approve --extract
flmint verify --profile stable --component daw-ge-proton
```

Commands refuse on purpose (exit `2`, with a `next action:` hint) when something is missing or unsafe:

- `launch` without `--approve` or a snapshot choice
- `launch` when Wine is already running in the prefix
- `launch` when the prefix sets winex11 `UseXRandR`/`UseXVidMode` to `N` (that crashed Xorg on this host)
- `install` without `--dry-run`
- the `diagnose` and `bench` stubs

## Status

| Area | Status |
| --- | --- |
| Host inventory, plan, pinned fetch/verify, snapshots | `verified` |
| FL Studio install (silent) in managed prefixes | `verified` |
| `flmint launch` / `stop` / `new-project` | `verified` (2026-11-05) |
| Save/reopen via launch-with-path + Ctrl+S | `verified` |
| File > Open / Save As dialogs | `blocked` (Wine bug) |
| PipeASIO audio at 256 samples | `partial`: starts and plays; formal latency not measured |
| FLEX and Direct3D plugins (experimental prefix) | `verified` after the vkd3d DLL and Verdana fixes |
| WAV export, recording, third-party plugins, latency benchmarks | `not tested` |

Tests and linters: `bash scripts/smoke_test.sh` runs pytest, ruff and mypy.

## Learn more

- `AGENTS.md` / `CLAUDE.md`: rules for AI agents working on this repo (kept in sync).
- `HANDOFF.md`: full operating policy and history.
- `docs/plan.md`: forward plan. `docs/architecture.md`: modules and safety invariants.
- `docs/rollback.md`: what snapshots do and don't cover. `docs/runbook.md`: commands and exit codes.
- `docs/compatibility-matrix.md`, `docs/benchmarks.md`, `docs/upstream-research.md`,
  `docs/os-migration-decision.md`.
