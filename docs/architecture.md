# Architecture

`flmint` is a planning/verification toolkit with an approval-gated launcher; it is not an installer.
Everything that mutates the host is behind an explicit refusal or an `--approve` flag.

## Module map (`src/flmint/`)

| Module | Role | Status |
| --- | --- | --- |
| `cli.py` | argparse surface: `doctor`, `plan`, `install`, `fetch`, `verify`, `launch`, `stop`, `new-project`, `snapshot`, `diagnose`, `bench`; converts `FlmintError` into exit code 2 with `next action:` lines | implemented |
| `probe.py` | `CommandProber`: subprocess wrapper with timeouts, argv lists (no shell), graceful "absent" results | implemented, tested |
| `doctor.py` | read-only host facts (`HostFacts`): os-release, kernel, CPU/memory, disk, GPU/driver/CUDA, audio stack, Flatpak/Wine/Docker presence, blockers/warnings | implemented, tested |
| `installer.py` | read-only installer validation: streaming SHA-256, minimal PE header parse (`pe_arch`, magic, subsystem), NSIS engine sniffing | implemented, tested |
| `manifest.py` | dependency-free YAML-subset loader + profile validation (`Profile`, `Component`, `Gate`) | implemented, tested |
| `planner.py` | deterministic `Plan`: gates, ordered steps with `approval_required`/`blocked`/`depends_on`, blockers, warnings, next actions | implemented, tested |
| `installer_runner.py` | **the approval boundary**: `perform_install()` always raises `ApprovalRequiredError`; `render_dry_run()` re-renders the plan | implemented, tested |
| `snapshots.py` | create/list/restore prefix snapshots inside managed state, verified archives, preserved rollbacks | implemented, tested |
| `runtime.py` | candidate runtime registry (`CANDIDATE_VERSIONS`, all `candidate-unverified`) + `MANAGED_STATE_DIRS` | implemented |
| `audio.py` | PipeWire/PipeASIO gate constant (`PIPEWIRE_PIPEASIO_MIN = 1.4.2`) + audio facts helpers | implemented |
| `state.py` | `safe_relative_path` (refuses traversal/absolute), `atomic_write_text` | implemented, tested |
| `errors.py` | `FlmintError`, `FlmintUsageError`, `ManifestError`, `ProbeError`, `ApprovalRequiredError`, `SnapshotError`, `NotYetImplementedError` | implemented |
| `runtime_launcher.py` | `build_spec` (clean env + argv, preflight: prefix, pinned runner, X11 hazard refusal, vkd3d/font warnings), `running_pids`, detached `start`, `stop` (`wineserver -k`) | implemented, tested; real launch + stop `verified` 2026-11-05 |
| `projects.py` | FL install/template discovery, `new_project` (no-clobber copy into `~/.local/share/flmint/projects`) | implemented, tested |
| `diagnostics.py`, `benchmarks.py` | Phase 2/3/5 stubs raising `NotYetImplementedError` | stubs (intentional) |

## Control flow

```
doctor  -> HostFacts (facts + blockers + warnings)
plan    -> HostFacts + Profile(+ optional InstallerInfo) -> Plan (steps/gates/blockers/warnings)
install --dry-run -> render_dry_run(Plan)          # no mutation
install           -> ApprovalRequiredError          # always, by design
launch  -> build_spec (no exec) -> --dry-run prints | --approve + snapshot choice -> start (detached)
stop    -> runner wineserver -k (prefix-scoped)
new-project -> copy template into managed projects dir (no clobber)
diagnose/bench -> NotYetImplementedError            # Phase 2/3/5 boundary
snapshot create/list/restore -> managed-state writes only, refuses without a prefix
```

## Safety invariants

1. **Side-effect-free by default.** `doctor`, `plan`, `install --dry-run`, and installer validation
   perform no downloads, no prefixes, no package installs, no installer execution.
2. **Approval boundary is code, not prose.** `perform_install()` raises
   `ApprovalRequiredError`; no flag today bypasses it.
3. **Writes are confined to managed paths** — `~/.local/share/flmint`, `~/.local/state/flmint`,
   `~/.local/opt/flmint` (XDG-aware), plus repo-relative paths validated by `safe_relative_path`.
   Never `~/.wine`, never system directories, never another tool's data directory.
4. **Every plan step declares `approval_required` and `blocked`.** Steps that create or run
   host-visible software (runner downloads, prefix creation, installer execution, activation, audio
   configuration) are `[approval]`; only managed-state-dir creation, read-only installer verification
   and snapshot writes are `[auto]`, and those write solely under `flmint`-managed paths.
5. **Candidates stay candidates.** `CANDIDATE_VERSIONS` entries are `version=None`; the planner emits
   `<VERSION-TO-PIN>` plus unpinned warnings until a human pins version + SHA-256 in the profile.
   `profiles/stable.yaml` is pinned by the 2026-11-03 decisions; `profiles/experimental.example.yaml`
   is still candidate-only.
6. **Probes are non-privileged and bounded.** Subprocess timeouts, argv-only invocation, absent
   tools degrade to recorded `absent` facts instead of crashing.
7. **Test hooks are explicit.** `FLMINT_OS_RELEASE` overrides the os-release path for tests only.

## Intentional gaps

- No download/verification engine yet: `flmint` plans downloads and records digests, it does not
  fetch them.
- No audio measurement yet: `bench audio` is a stub; `wpctl`/`pw-dump` facts are collected but not
  analyzed.
- No diagnostics bundle yet: `diagnose` is a stub; the plan already reserves
  `~/.local/state/flmint` for it.
