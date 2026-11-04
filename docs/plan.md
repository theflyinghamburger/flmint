# Execution plan (living)

Owner: human (approval authority). Executor: `flmint` agents. This file is the forward plan; the
record of what has already happened is `HANDOFF.md` sections 16-17 and `reports/phase-0-summary.md`.

Phase status: **Phase 0 complete**, **non-destructive Phase 1 complete**, **Phase 2.2 + 2.3 + 2.4 done**
(pinned runner fetched, digest-matched and extracted under `~/.local/opt/flmint/daw-ge-proton/`; isolated prefix
created at `~/.local/share/flmint/profiles/stable/prefix`; FL Studio 2026 installed in that prefix via a
supervised silent `/S` installer run — `reports/runner-install-phase2.md`). D1-D3 and D5 were answered on
2026-11-03 (recorded in `reports/decisions.md`); D4 has since been cleared manually by the owner, so Phase 2
activation/save/export and Phase 5 are no longer decision-blocked, though they remain untested. D5 option (a) was
executed by the owner (`sudo apt install libc6-i386`, `2.44-1ubuntu2`), then approved owner-run `lib32gcc-s1` and
i386 GUI packages were used during the 2.4 retry path; `flmint` ran no `sudo`/`apt`. The installer has run silently
and FL Studio files are installed; supervised launch/manual-auth and PipeASIO 512/256 launch tests have occurred,
but **activation is not yet measured**, full launch stability remains unverified, and `~/.wine` remains absent.

## 1. Decision gates (blocking, human answers required)

| ID | Question | Options | Proposal (not approved) | Consequence if skipped |
| --- | --- | --- | --- | --- |
| **D1** | Runner architecture | (a) Flatpak Bottles 67.5 only — no PipeASIO ever; (b) pinned native Wine/Proton under `~/.local/opt/flmint/<runner>/<version>` — PipeASIO-capable; (c) both (native primary, Bottles for GUI convenience) | **(b) native pinned runner** as primary: it is the only path PipeASIO upstream supports, it keeps prefixes in `flmint`-managed paths, and it avoids writing into another app's data dir | Phase 3 has no supported low-latency path; hidden unpinned Wine gets pulled in ad hoc |
| **D2** | Exact pins + digests written into `profiles/*.yaml` | pin or refuse | Pin: Bottles `67.5` (Flathub, GPL-3.0-only), `DAW-GE-Proton11-6c` `aecf5951…f02d5`, PipeASIO `v1.10.0` (AppImage `cc486351…29da`, Arch tarball `54f95938…7a5b`), WineASIO `v1.3.0` `f8bf74c8…6a4c`. **Wine version still unresolved (source unreachable)** | `plan` keeps emitting "unpinned" warnings and any install is unreproducible |
| **D3** | Installer provenance | (a) accept `26.1.7.5654` with recorded SHA-256 `6ddf9f23…4edca` and test the WinTrust claim in an isolated prefix; (b) look for an official older installer; (c) stop | **(a)**, because the WinTrust claim is unverified and testing it is cheap once a prefix exists — with the explicit rule: no third-party installer mirrors | Phase 2 cannot begin; guessing wastes an approval cycle |
| **D4** | Validation inputs | provide unlocked Image-Line license path (trial cannot reopen saved `.flp`) + user-owned model for the AI track | **Manually cleared by owner 2026-11-03**; actual license/model evidence still needs testing | Save/reopen and AI coexistence gates become testable but remain unverifiable until measured |
| **D5** | Host 32-bit loader for the multilib runner (new, 2026-11-03) | (a) `sudo apt install libc6-i386` (reversible); (b) container-based runner (`podman` + i386 image); (c) re-pin to a 64-bit-only Wine build; (d) stop Phase 2 | **(a)**: smallest distro-supported change and the only one keeping D1/D2 intact | Step 2.3 cannot run, so the whole isolated-prefix chain (2.3-2.9) and Phase 3 stall |

**Answers recorded 2026-11-03 in `reports/decisions.md`:** D1 = (b) pinned native runner (Bottles removed
from `profiles/stable.yaml`; PipeASIO deferred to a separate experimental prefix in Phase 3). D2 = pin
`DAW-GE-Proton11-6c` (`aecf5951…f02d5`) and treat its bundled Wine as the runner; distro
`wine 10.0~repack-12ubuntu1` rejected because it predates PipeASIO's `wine-11.18` build SDK; the bundled
Wine is now measured as `wine-11.0 (Staging)` (`reports/runner-install-phase2.md`), which makes PipeASIO
compatibility with the pinned runner `unverified` rather than assumed. D3 = (a) accept `26.1.7.5654`
(`6ddf9f23…4edca`) and measure the WinTrust claim in the isolated prefix; no third-party mirrors.
D4 = manually cleared by the owner on 2026-11-03: 2.5 activation, supervised launch validation, 2.7 save/reopen +
WAV export, and Phase 5 are no longer decision-blocked, but remain `not tested` until measured. **D5 = answered +
executed (option (a))** on 2026-11-03: the owner installed `libc6-i386`,
`/lib/ld-linux.so.2` now exists, the prefix + `baseline` snapshot followed (`~/.wine` still absent), and 2.4 was
later completed as a silent `/S` install after owner-run `lib32gcc-s1` and i386 GUI package support.

Pinned plan + dry-run reruns: `reports/plan-stable-pinned.txt` and
`reports/install-dry-run-stable-pinned.txt` (zero unpinned warnings; `install` without `--dry-run` still
exits 2). Planner fix 2026-11-03: step 4 prefix creation is now flagged `[approval]` (it was `[auto]`,
which contradicted this plan's own gate), and the "pin exact versions" next action is only emitted when a
plan actually has unpinned components. Backlog item 3 (refusing a plan as installable unless every
download/build component carries a digest) is **still open**.

Answer format expected in `reports/decisions.md` (created 2026-11-03): decision ID, chosen option,
who approved, date, pinned version + digest, and any scope limit.

## 2. Safe work that can proceed **without** new approvals (backlog)

These touch only the repo or read-only host facts. Each item must land with tests + `ruff` + `mypy` green.

1. **`downloads.py` (dry-run form only):** declared-artifact model, digest verification function,
   provenance record writer; unit-tested with fake files and mocked HTTP; no network by default.
2. **`diagnose` real implementation:** collect `doctor` JSON + managed logs + snapshot metadata into a
   `reports/` tar.gz with sanitization (strip usernames/paths/tokens), refuse to include private project
   dirs; tests for sanitization.
3. **`plan` hardening:** require every `download`/`build` component to have a pinned digest before a
   plan can be marked installable (currently only a warning).
4. **Doctor drift detection:** `doctor --compare <prior.json>` reporting what changed between audits.
   **Done 2026-11-03:** compares material facts/capabilities/blockers, ignores generated timestamps and probe
   logs, exits `0` when clean and `1` when material drift is found. Post-D5 audit:
   `reports/host-audit-2026-11-03-post-d5.json`.
5. **Prefix-launch scaffolding behind the approval flag:** argv construction with explicit `WINEPREFIX`,
   env isolation tests, no execution.

Explicitly **not** backlog-able without approval: any download, `flatpak --user install`, extraction,
prefix creation, installer execution, activation, package installs (incl. JACK), realtime scheduling, benchmarks.

## 3. Phase 2 — stable install (starts only after D1-D3)

Order matters; each step ends with a snapshot and a `reports/` note.

| # | Task | Deliverable | Gate |
| --- | --- | --- | --- |
| 2.1 | Write pins into `profiles/stable.yaml`; rerun `plan` + `install --dry-run` | `reports/plan-stable-pinned.txt`, zero unpinned warnings | human sign-off on the pinned plan |
| 2.2 | Fetch/verify runner artifact **only** against pinned digests | `reports/provenance-<runner>.json` | digest match mandatory, else stop |
| 2.3 | Create isolated prefix in `~/.local/share/flmint/profiles/stable/prefix` with explicit `WINEPREFIX` | prefix + `snapshot create --name post-prefix` | `~/.wine` still absent |
| 2.4 | **Done as a silent `/S` run (2026-11-03)** — supervised execution of the official installer inside the managed prefix; interactive GUI attempts remain unverified/glitched | install log in `~/.local/state/flmint/logs/`, snapshots `pre-installer-silent-2026-11-03` and `post-installer-silent-2026-11-03` | human present; orphan-process check; WinTrust outcome recorded as "no WinTrust error text observed", not full certificate validation |
| 2.5 | Legitimate activation (user's own account), documented failure modes | activation note + `snapshot create --name post-activation` | no license bypass, WebView2 failures logged not worked around |
| 2.6 | `launch` implemented against the pinned runner + desktop entry | pinned argv, prefix isolation tests | 20 consecutive launch/exit runs, no orphaned critical processes |
| 2.7 | Save/reopen + offline WAV export on a human-authored test project | test project + exported file + hashes | requires D4 license |
| 2.8 | Rollback rehearsal | `snapshot restore` recovers a prefix after a simulated bad change | project files untouched |

**Phase 2 gate (unchanged from HANDOFF §8):** a human confirms real UI launch, legitimate activation,
save/reopen works, offline WAV export succeeds. Partial success must be reported as partial.

## 4. Phase 3 — audio validation (after Phase 2 passes)

1. Baseline first: FL Studio built-in ASIO / Wine audio, Scarlett Solo, 48 kHz, 1024 → 512 → 256 frames.
2. Then one experiment per prefix, snapshot before/after: PipeASIO (needs D1=b) or WineASIO (needs approved
   `jackd` install + realtime policy discussion).
3. Per row evidence: `pw-dump`/`wpctl status` capture, `mpstat` CPU, XRUN evidence if obtainable, snapshot
   name, pinned runner version. No latency number without loopback measurement.
4. Gate: 30 min clean playback at the chosen stable buffer, then a 4-hour soak. No permanent governor/RT changes.

## 5. Phase 4 — plugins and graphics

- Inventory the plugins actually owned + one freely downloadable plugin for reproducibility.
- Fill `docs/compatibility-matrix.md` rows: plugin/vendor/version, runner, result, workaround.
- Only reproduce a Wine/WinTrust/WebView2/Direct2D/JUCE issue locally before considering any patch, and a
  patch needs a failing-then-passing test plus a rollback snapshot.

## 6. Phase 5 — performance and AI coexistence (needs D4 model)

- `llama.cpp` with the user-supplied model + recorded model SHA-256; `nvidia-smi` + `mpstat` sampling.
- Rows: FL Studio idle, playback alone, playback + CPU stress, playback + GPU inference (never during recording).
- Report medians + spread, same model/runner/buffer/interface for every comparison.

## 7. Phase 6 — packaging and maintenance

- Lockfile with exact versions + digests + source URLs; `flmint uninstall` scoped to `flmint`-owned state only.
- Second clean environment reproduces everything from the official installer + documented prerequisites.
- Re-verify the whole matrix if the base distro changes (26.10 loses standard maintenance Jul 2027; a fresh
  26.04 LTS install is a separate, human-approved maintenance milestone).

## 8. Standing rules for every work item

1. Snapshot before mutating a prefix; verify archive SHA-256 before restoring.
2. Writes only under `~/.local/{share,state,opt}/flmint` or repo-relative paths.
3. One variable per experiment; revert on regression; record command + exit status.
4. Status labels in every report: `verified` / `unverified` / `hypothesis` / `not tested` / `blocked`.
5. `pytest`, `ruff check src tests`, `mypy` green before a change is called done.
6. Never claim FL Studio, VST, latency, or GPU results without captured evidence.
