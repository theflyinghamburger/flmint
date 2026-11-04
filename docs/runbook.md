# Runbook

Safe-by-default operations for this repository. Commands that mutate the host are listed as
**approval-required** and are not runnable today.

## 0. Environment setup

```bash
cd ~/code/misc/fl_studio_port
python3 -m venv .venv                       # if missing
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check src tests
.venv/bin/mypy
```

Current recorded results: `69 passed, 14 subtests passed`, `All checks passed!`,
`Success: no issues found in 17 source files`.

Python requirement: `>=3.12` (PEP 604 unions, `datetime.UTC`, `tarfile` `filter=` keyword).

## 1. Routine safe commands (no side effects)

```bash
.venv/bin/python -m flmint doctor --format text
.venv/bin/python -m flmint doctor --format json --save reports/host-audit.json
.venv/bin/python -m flmint plan --installer "$HOME/Downloads/flstudio_win64_26.1.7.5654.exe" --profile stable
.venv/bin/python -m flmint install --installer "$HOME/Downloads/flstudio_win64_26.1.7.5654.exe" --profile stable --dry-run
.venv/bin/python -m flmint snapshot list --profile stable
```

Expected: exit `0`. `doctor --save` is the only routine command that writes, and it writes a
repo-relative report after `safe_relative_path` validation.

## 2. Commands that intentionally refuse (know the exit codes)

| Command | Today's behavior | Exit |
| --- | --- | --- |
| `flmint install ...` (no `--dry-run`) | `ApprovalRequiredError` | `2` |
| `flmint launch` (no `--approve`, or no `--snapshot NAME` / `--no-snapshot`) | `ApprovalRequiredError` | `2` |
| `flmint launch` with Wine running in the prefix, or `UseXRandR`/`UseXVidMode`=`N` set | refusal | `2` |
| `flmint snapshot create --profile stable --name baseline` | `no prefix to snapshot ...` | `2` |
| `flmint diagnose --profile stable` | `NotYetImplementedError` (Phase 2+) | `2` |
| `flmint bench audio --profile stable` | `NotYetImplementedError` (Phase 3) | `2` |
| `flmint bench ai --model X` | `NotYetImplementedError` (Phase 5) | `2` |

Errors print `flmint error: <message>` followed by `  next action: ...` lines; there are no stack
traces for ordinary missing-dependency cases.

## 3. Before any Phase 2 mutation (checklist)

1. `flmint doctor` → confirm nothing regressed (Wine still absent, PipeWire/driver unchanged).
2. `flmint plan` + `flmint install --dry-run` → read every `[approval]` and `[BLOCKED]` step.
3. Pin versions + SHA-256 in the profile (edit `profiles/<name>.yaml`; never rely on "latest").
4. Confirm the installer SHA-256 against the official download page / provenance decision.
5. Get explicit human approval for each `[approval]` step; record who approved what.
6. Only then implement/run the approved step, and **immediately** take a baseline snapshot:
   `flmint snapshot create --profile <name> --name post-install`.

## 4. Snapshots and rollback

```bash
flmint snapshot create  --profile stable --name post-install
flmint snapshot list    --profile stable
flmint snapshot restore --profile stable --name post-install
```

State lives under `~/.local/share/flmint/profiles/<profile>/` (prefix, `snapshots/`,
`prefix.discarded-<stamp>`). Restore verifies the archive SHA-256 first and never deletes the
prefix it replaces. See `docs/rollback.md` for guarantees and known limits.

Manual cleanup of `prefix.discarded-*` is a human decision after a confirmed-good restore.

## 5. If something breaks (Phase 2+)

1. Stop. Do not "fix" by editing system config or global Wine settings.
2. Re-run `flmint doctor --format json --save reports/host-audit-broken.json` for a fact snapshot.
3. `flmint snapshot list` → restore the last known-good snapshot.
4. Write a short incident note in `reports/` with: command, exit code, pinned runner version,
   snapshot name, symptom, and what changed since the last good snapshot.
5. Reproduce the smallest failing step before changing anything else.

Secrets hygiene: diagnostics bundles must be inspected before sharing; do not include account
tokens, activation data, or private project contents.

## 6. Removing only project-owned state

There is no `flmint uninstall` command yet (Phase 6). Until then the manual scope is:

```bash
rm -rf ~/.local/share/flmint ~/.local/state/flmint ~/.local/opt/flmint
```

That removes only `flmint`-owned state. It does **not** remove Flatpak apps, system packages, or
`~/.wine` (which this project never creates). Confirm `~/.wine` non-existence before and after
(`ls -d ~/.wine`) so accidental coupling to a pre-existing prefix is visible.

## 7. Approval-required actions that are explicitly *not* scripted here

- `flatpak --user install com.usebottles.bottles <pinned-version>`
- downloading/extracting any runner (Wine/Proton), PipeASIO, or WineASIO artifact
- installing JACK/`qjackctl` or changing realtime scheduling limits
- executing the FL Studio installer or activating a license
- any GPU/AI benchmark run against user models

Each of these needs a human decision, a pinned version + digest, and a snapshot taken first.
