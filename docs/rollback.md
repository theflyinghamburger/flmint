# Snapshot and rollback contract

Implementation: `src/flmint/snapshots.py` (create / list / restore), CLI `flmint snapshot ...`.
Tests: `tests/test_snapshots.py`, `tests/test_cli.py`.

Snapshots exist for one reason: every Phase 2 prefix mutation must be reversible without touching
anything outside `flmint`'s own directories. Until a prefix exists, the module intentionally refuses
to write anything.

## Paths (project-managed only)

```
~/.local/share/flmint/profiles/<profile>/prefix              # the Wine/Proton prefix (Phase 2 creates it)
~/.local/share/flmint/profiles/<profile>/snapshots/<name>.tar.gz
~/.local/share/flmint/profiles/<profile>/snapshots/<name>.json
~/.local/share/flmint/profiles/<profile>/prefix.discarded-<UTC stamp>
```

- Root respects `XDG_DATA_HOME` (falls back to `~/.local/share`), plus an explicit `state` argument
  used by tests. Nothing is ever written under `~/.wine`, `/etc`, `/usr`, or another tool's prefix.
- Profile names and snapshot names must be a **single path component**; `..`, `/`, and absolute
  paths are rejected as `SnapshotError` (exit code 2).
- Temp archive files are named `.<name>.tar.gz.tmp-<pid>` and moved into place with `os.replace`.

## Commands

```bash
flmint snapshot list   --profile stable
flmint snapshot create --profile stable --name baseline
flmint snapshot restore --profile stable --name baseline
```

Current real-host behavior (verified read-only, no files created):

- `list` with no state → `no snapshots for profile 'stable'`, exit `0`.
- `create` with no prefix → exit `2`, message `no prefix to snapshot for profile 'stable': ...`,
  with next actions pointing at `flmint plan` and the Phase 2 approval boundary.
- `flmint install` **without** `--dry-run` always raises `ApprovalRequiredError`; there is no code
  path that creates a prefix today, so snapshots are "ready but gated".

## Guarantees implemented

1. **Verified restore.** `restore` recomputes the archive SHA-256 and refuses if it does not match
   the recorded digest, or if no digest was recorded. An unverified archive is never used.
2. **Layout enforcement.** Extraction is refused unless every member lives under a single `prefix`
   tree, extracted into a staging directory first (`filter="tar"`).
3. **Nothing is silently deleted.** A replaced prefix is renamed to
   `prefix.discarded-<stamp>` and reported. Users delete discarded prefixes manually only after
   confirming the restore is good.
4. **No silent overwrite.** Creating a snapshot name that already exists is refused.
5. **Disk headroom check.** Free space must cover `~1.2 × prefix bytes + 256 MiB`; otherwise the
   operation is refused before writing.
6. **Missing archive is reported, not removed.** `list` reads metadata JSON, so an archive that was
   deleted elsewhere shows as `MISSING ARCHIVE`.

## Known limits (do not oversell these)

- Snapshots cover the **prefix tree only**. They do not capture Wine/Proton binaries, Flatpak runtimes,
  system packages, drivers, `~/.config` changes made by Wine itself outside the prefix, or the Windows
  installer file.
- Prefix trees can contain sockets, symlinks, and files with unusual modes; `tar` round-trip behavior
  for a **real Wine prefix has not been tested on this host** (`not tested`).
- Snapshots are local to this machine; there is no encryption, no off-host backup, and no
  incremental/deduplicated archive yet.
- Concurrency is unmanaged: two simultaneous `create`/`restore` calls on one profile are not
  serialized (`not tested`).
- Restore swaps directories with `os.replace`; it is atomic per directory but not a transaction across
  a crash. A crash mid-restore can leave a staging directory behind; it is never auto-deleted.

## Rollback playbook (the human-facing procedure)

1. Before any Phase 2 change, run `flmint plan` and `flmint install --dry-run`, then read the plan.
2. Create a baseline snapshot **immediately after the first successful install step** and before any
   experimental tweak (runner swap, DLL registration, font/renderer toggle, plugin install).
3. Name snapshots by intent and time, e.g. `2026-11-03-post-install`, `pre-runner-swap`.
4. If an experiment degrades audio/GUI, restore the last known-good snapshot and re-test the smaller
   change separately.
5. Record restore outcomes in `reports/` (command + exit status) so a regression is attributable.
6. Delete `prefix.discarded-*` only after confirming the restored prefix behaves correctly.
