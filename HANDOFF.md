# Project Handoff: FL Studio on Linux + Local AI Workstation

**Project codename:** `flmint`  
**Prepared for:** OpenCode (local LLM coding harness)  
**Handoff date:** 2026-11-03  
**Status:** Design and implementation brief. **No installer, runner, patch, or host change has yet been implemented or validated by this handoff.**

> **Instruction to the coding agent:** You are the implementation owner. Start by inspecting the actual workstation, verifying upstream requirements, and delivering a small, tested, non-destructive vertical slice. Do not treat the design assumptions below as observations. Favor reversible, measured changes over speculative optimization. Do not silently modify the host operating system.

---

## 1. Objective and definition of success

Build a **reproducible, version-pinned FL Studio compatibility and performance toolkit for Linux** that starts from an **official user-supplied FL Studio Windows installer** (`.exe`). This workstation must also remain a reliable development and **local NVIDIA AI inference** machine.

Top-level objectives, in priority order:

1. **Reliability:** FL Studio launches, activates through legitimate methods, plays audio, saves/reopens projects, renders files, and survives long sessions without corrupting data.
2. **Reproducibility:** A documented set of exact versions and checksums reproduces a working Wine/Proton environment; updates have rollback.
3. **Audio performance:** Tune PipeWire/ASIO with documented latency/underrun tests; do not confuse reported buffer latency with measured round-trip latency.
4. **Windows plugin compatibility:** Support common VST2/VST3 plugins through an explicit compatibility matrix, without claiming universal support.
5. **Workstation coexistence:** Preserve NVIDIA driver/CUDA, Docker, `llama.cpp`, and `vLLM` capability. Keep the AI and DAW environments independently maintainable.
6. **Developer experience:** One CLI for inspection, installation planning, installing approved components, launching, diagnostics, snapshots, and benchmarks.

**Success is not** “FL Studio starts once.” The project succeeds when the behavior is tested, repeatable, observable, recoverable, and documented.

### Out of scope / constraints

- Do not reverse engineer or redistribute proprietary Image-Line binaries, license material, plugins, or installers.
- Do not bypass activation, digital signatures, DRM, iLok, or paid plugin licensing.
- Do not replace the Linux kernel, distribution, system Wine, NVIDIA driver, system PipeWire, or default Python without specific human approval.
- Do not perform any unattended OS migration or destructive partitioning.
- Do not put user credentials, project files, license keys, or private model paths in published logs.
- Do not promise full compatibility or better-than-Windows latency before benchmarks.

---

## 2. Known context vs things to discover

### User-provided context to preserve

- The user has been using / considering **Linux Mint 22.3 XFCE** and is interested in **Xubuntu 26.04 LTS**, optionally with Ubuntu Studio's audio facilities. **The actual currently booted OS is NOT confirmed here.**
- Desktop for local AI: **NVIDIA RTX 3090, 24 GB VRAM; 64 GB DDR4 RAM**. Confirm with host detection rather than assuming this exact machine is running the agent.
- Relevant workloads: `llama.cpp`, `vLLM`, local quantized LLMs, general software development and OpenCode-based agentic coding.
- FL Studio must run via the **official Windows installer** on Linux with strong stability, low-latency audio, and Windows plugin support.
- Previous intensive parallel build/agent workloads caused severe CPU/RAM/disk contention on a machine. **Default to bounded parallel work.**

### Mandatory discovery at the start

Determine and write down:

- Distribution, release, desktop session (`X11` vs Wayland), kernel, CPU, RAM, filesystems, free disk space and free inodes.
- GPU + loaded NVIDIA driver, working `nvidia-smi`, CUDA toolkit presence, Docker/Podman availability.
- PipeWire and `pipewire-pulse` versions, `wpctl`, `pw-cli`, `pactl`, JACK compatibility and installed audio devices.
- Wine, Bottles (Flatpak), Flatpak/Flathub, existing Wine prefixes, previous FL Studio installations.
- Location, signature/hash, apparent version and source of the FL Studio Windows installer **if one was supplied**; otherwise implement a `--installer` input and report the pending prerequisite without inventing a path.
- Audio interface type (USB/PCI/onboard), sample rates, buffer settings; if unknown, mark unknown.
- Which existing data must be retained, and location of backups. Do not read private music projects unless necessary and authorized.

**Never assume the workstation is running Xubuntu merely because it was recommended in prior discussion.**

---

## 3. OS strategy and operating principles

**Preferred future host:** Xubuntu 26.04 LTS (XFCE) with appropriate Ubuntu Studio audio tooling, conditional on actual hardware testing. Ubuntu Studio 26.04 LTS is a valid alternative for a predominantly audio-production workstation. Neither choice intrinsically accelerates CUDA inference.

**Important distro compatibility gate:** PipeASIO currently documents **PipeWire >= 1.4.2** as a build/runtime prerequisite. Stock Ubuntu 24.04-family packages (the base used by Mint 22.x) have historically carried older PipeWire versions. Verify the *installed* version before choosing an audio path; do not blindly add repositories or replace PipeWire system-wide. Ubuntu 26.04's newer stack may reduce this problem, but still inspect actual versions.

**Deployment rule:** Treat OS selection/migration as a **separate, human-approved workstream**. Build `flmint doctor` and the compatibility installer to support the current host where feasible; recommend a migration only if clearly justified by measured or documented blockers.

**Default environments:**

- **Stable:** an isolated Wine/Bottles environment with a pinned, known-working runtime, FL Studio's supplied ASIO path as initial audio baseline.
- **Experimental:** a separate prefix and potentially patched Wine runner; PipeASIO where requirements are met, or WineASIO/JACK where suitable.
- **AI:** existing host CUDA driver plus isolated containers/venvs for inference, with separate benchmark scripts and artifacts.

Avoid altering the production prefix to test experimental audio drivers or registry overrides.

---

## 4. Relevant upstream projects and what to verify

These are leads, **not automatically endorsed installer dependencies**. Check the README, release date, compatibility claims, licenses, commit hashes, build instructions, and open issues on the day of implementation.

| Project / reference | Purpose | URL |
| --- | --- | --- |
| Image-Line | Official FL Studio installer, account/licensing, release notes | https://www.image-line.com/fl-studio-download/ |
| Community FL Studio Linux setup | Bottles installation and recent Wine certificate workaround | https://github.com/Torbuntu/fl-studio-linux-setup |
| DAW-GE-Proton | Candidate customized runner, version must be pinned | https://github.com/KitsuneDev/daw-proton-ge |
| Bottles | Wine prefix and runner management | https://usebottles.com/ |
| PipeASIO | Native PipeWire ASIO bridge | https://github.com/M0n7y5/pipeasio |
| WineASIO | ASIO-to-JACK bridge | https://github.com/wineasio/wineasio |
| Wine upstream | Wine source, releases, compatibility fixes | https://gitlab.winehq.org/wine/wine |
| WinTrust issue/patch | Relevant for some FL Studio 26.x certificate-verification failures | https://gitlab.winehq.org/wine/wine/-/merge_requests/11824 |
| Advanced case study | Patched Wine, WebView2, JUCE/VST/iLok experiments; treat as single-machine results | https://pr1v8.ca/posts/fl-studio-wine-plugins-ilok/ |
| NVIDIA CUDA documentation | Driver/toolkit compatibility by distribution and release | https://docs.nvidia.com/cuda/cuda-installation-guide-linux/ |
| Ubuntu Studio 26.04 | Audio-focused distro/tools and current release details | https://wiki.ubuntu.com/Ubuntu_Studio/26.04 |
| OpenCode instructions | How project `AGENTS.md` is loaded | https://opencode.ai/v2/docs/instructions |

**Upstream research tasks:**

1. Verify whether the FL Studio WinTrust issue is already fixed in a recent stable Wine build. If yes, do **not** carry redundant patches.
2. Verify DAW-GE-Proton archive structure and whether it can safely be used as a Bottles runner on this host. Pin exact release + SHA-256.
3. Determine PipeASIO build/registration requirements for **this exact Wine/Proton runner**, including matching Unix and PE DLL paths and potential Flatpak sandbox constraints.
4. Check if WebView2/FL Cloud features are needed for acceptance; separate core DAW functionality from cloud/browser integrations.
5. Check current Ubuntu Studio installer behavior before writing packages into an automatic installation script.

---

## 5. Architecture

```text
                               flmint CLI
  doctor | plan | install | launch | snapshot | restore | diagnose | bench
                                  |
              +-------------------+-------------------+
              |                                       |
     Host capability scanner                    Dependency resolver
    OS/GPU/PipeWire/audio/etc.                 version + SHA + gates
              |                                       |
              +-------------------+-------------------+
                                  |
                            Install planner
                     dry-run, approval gates
                                  |
               +------------------+-------------------+
               |                                      |
         Stable environment                    Experimental environment
        isolated Wine/Bottles                  isolated patched Wine
         pinned Windows prefix                 separate Windows prefix
           FL Studio + VSTs                     FL Studio + VSTs
               |                                      |
    built-in FL Studio ASIO                      PipeASIO / WineASIO
               +------------------+-------------------+
                                  |
                           PipeWire / ALSA
                                  |
                         Host audio hardware

          Independent AI environment (CUDA + llama.cpp/vLLM)
             metrics only; no DAW prefix or audio mutation
```

### Isolation requirements

- Store application environments, manifests, scripts, and logs under a project-managed, user-writable path, default `~/.local/share/flmint/` for state and `~/.local/state/flmint/` for logs, respecting XDG paths.
- The repository contains **source/config/tests only**, never private Windows installers or proprietary plugins.
- For the stable implementation, investigate Bottles integration first. If it is unreliable to automate safely, support a direct standalone Wine prefix with a reproducible shell/Python runner wrapper and document tradeoffs.
- The experimental Wine build must use a private installation prefix (e.g. `~/.local/opt/flmint/wine/<version>`).
- Do not mutate the user's `~/.wine`, arbitrary Bottles entries, or system-wide Windows DLL registrations.
- Every tool invocation using a prefix must explicitly set its own `WINEPREFIX` and runner binary.

---

## 6. Proposed repository layout

```text
flmint/
├── AGENTS.md                     # Concise always-on OpenCode project rules
├── HANDOFF.md                    # Copy of this specification
├── README.md                     # User-facing quickstart / compatibility status
├── pyproject.toml                # Python 3.12+ tooling and CLI
├── src/flmint/
│   ├── __main__.py               # python -m flmint
│   ├── cli.py
│   ├── doctor.py
│   ├── manifest.py
│   ├── planner.py
│   ├── runtime.py
│   ├── installer.py
│   ├── audio.py
│   ├── snapshots.py
│   ├── diagnostics.py
│   └── benchmarks.py
├── profiles/
│   ├── stable.example.yaml
│   └── experimental.example.yaml
├── scripts/
│   ├── smoke_test.sh
│   └── collect_host_facts.sh
├── tests/
│   ├── test_doctor.py
│   ├── test_manifest.py
│   ├── test_planner.py
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── compatibility-matrix.md
│   ├── benchmarks.md
│   ├── os-migration-decision.md
│   ├── rollback.md
│   └── runbook.md
└── reports/                      # gitignored, sanitized machine results
```

**Language preference:** Python 3.12+ for orchestration, with small Bash helpers only where useful. Prefer standard library and typed, testable interfaces. Avoid hard-coding OS package names until detected. Do not add a GUI until CLI and rollback work.

---

## 7. CLI contract (design target, not implemented yet)

```bash
flmint doctor --format json
flmint doctor --format text
flmint plan --installer /path/to/flstudio_win64.exe --profile stable
flmint install --installer /path/to/flstudio_win64.exe --profile stable --dry-run
flmint install --installer /path/to/flstudio_win64.exe --profile stable
flmint launch --profile stable
flmint snapshot create --profile stable --name before-change
flmint snapshot list --profile stable
flmint snapshot restore --profile stable --name before-change
flmint diagnose --profile stable --output ./reports/diagnostics.tar.gz
flmint bench audio --profile stable --sample-rate 48000 --buffers 1024,512,256
flmint bench ai --model /path/to/model.gguf --backend llamacpp
```

- **`doctor`** never changes the system and exits with structured capability / blocker information.
- **`plan`** identifies exact steps, dependencies, downloads, disk estimates, risks, and human approval checkpoints. It does not install anything.
- **`install --dry-run`** must be side-effect-free; print a clear action plan.
- **`install`** may modify only project-managed user paths unless explicit approval for privileged operations is obtained. Missing prerequisites must be reported, not blindly installed with `sudo`.
- **`launch`** must use the exact pinned runner and prefix. No global Wine environment leakage.
- **`snapshot`** must capture prefix plus necessary metadata, verify disk space, and restore atomically if practical. Do not silently delete old snapshots.
- **`diagnose`** sanitizes usernames, access tokens, serials/license material and private file paths where possible.
- **`bench audio`** provides a reproducible manual/semi-automated test plan. Do not fabricate XRUN counts or physical round-trip latency if no reliable measurement instrument exists.
- **`bench ai`** never downloads a model without approval and must be allowed to skip when no model is provided.

---

## 8. Execution phases and acceptance gates

### Phase 0 — Read-only inventory and risk assessment (FIRST)

Deliverables:

- Implement `/doctor` (text and JSON), collect factual environment information, and identify supported/unsupported paths.
- Record results in `reports/host-audit.json`, gitignored by default.
- Capture versions including installed distro, session type, kernel, PipeWire, NVIDIA driver, CUDA tools, Wine, Bottles, Flatpak, filesystem headroom.
- Create `docs/os-migration-decision.md`: *current host vs Xubuntu 26.04 vs Ubuntu Studio 26.04*, with concrete compatibility gates. **Do not change OS.**
- Record expected FL Studio installer path status (`present/absent`) without searching private folders indiscriminately.

**Gate:** `doctor` runs as non-root, does not mutate system or private project data, and is unit tested with mocked command outputs.

### Phase 1 — Build the reproducibility and safety core

Deliverables:

- Project scaffolding (`pyproject.toml`, `src`, `tests`, CI-ready formatting/lint/test commands).
- Versioned manifest schema, installer path validation, SHA-256 calculation, architecture checks.
- Profile resolver with explicit prerequisites, compatibility gates, pinned tool checksums, package/source provenance.
- `plan` and `install --dry-run` with deterministic, understandable output.
- Structured errors with next actions, not stack traces for ordinary missing packages.
- `AGENTS.md` and user-facing README.

**Gate:** `pytest` passes, formatting/lint passes, missing installer and unsupported PipeWire versions are handled cleanly; no privileged operations execute.

### Phase 2 — Stable FL Studio installation (requires user-supplied installer and approval)

Deliverables:

- Evaluate Bottles runner automation; implement the most reproducible path with a pinned Wine/Proton runner.
- Preflight external download signatures/hashes, available disk space, and runtime provenance.
- Create isolated prefix; launch official installer; preserve the installer outside the repository; set up minimal dependencies only.
- Document legitimate Image-Line activation, including failure modes for embedded login/WebView2; do not bypass licensing.
- Detect app binary/desktop integration and create a launcher.
- Add per-profile `snapshot` and `restore` before implementing update flows.

**Gate:** human confirms actual UI launch, legitimate activation, a test project can save/reopen, and an offline WAV export succeeds. Report partial success accurately.

### Phase 3 — Audio backend and low-latency validation

Deliverables:

- Establish built-in FL Studio ASIO / Wine audio baseline, capturing effective sample rate, buffer sizes, and audible glitches.
- Verify PipeASIO >=1.4.2 PipeWire prerequisite; document runtime-specific registration and DLL locations. Use experimental environment.
- Where suitable, compare WineASIO/JACK bridging; account for Proton's runtime library constraints.
- Build manual test harness using a reproducible FL Studio test project (or clearly documented human-created fixture).
- Log CPU utilization, XRUN/underrun evidence where available, sample rate, buffers, interface name, and project complexity.
- Avoid permanent CPU governor changes or blanket real-time priority; test changes one at a time and revert on regression.

**Gate:** at least 30 minutes clean playback at the selected *stable* buffer size, then pursue 4-hour soak test. A claimed round-trip latency requires appropriate loopback measurement.

### Phase 4 — Plugin and graphics compatibility

Deliverables:

- Test representative VST2/VST3 plugins the user actually owns, plus at least one freely available plugin for reproducible CI/manual testing.
- Compatibility matrix: plugin/vendor/version, installer, UI, preset saving, automation, MIDI, rendering, licensing, result, runner/version, workaround.
- Evaluate upstream Wine fixes for WinTrust, WebView2, Direct2D, JUCE. Apply custom patches only if reproduced and not fixed upstream.
- Separate generic Wine improvements from vendor-specific workarounds; never globally override DLLs without reason.

**Gate:** consistent pass/fail results with logs and repro steps; any patch has a corresponding failing-then-passing test and rollback.

### Phase 5 — Performance regression and AI-workload coexistence

Deliverables:

- Baseline `llama.cpp` inference on RTX 3090 using **user-provided** model and command line; optional vLLM test in pinned container/venv.
- Capture GPU driver, CUDA runtime, model digest, quantization, context length, batch size, TTFT/tokens-per-second (where measured), VRAM, peak RAM, power/thermals.
- Compare FL Studio audio behavior when idle vs CPU stress vs GPU inference, but **do not run full-intensity GPU tests during an active recording session**.
- Build documentation for two host profiles: `music` (limit background load) and `ai` (throughput), with no undocumented host mutations.
- Use repeatable workload definitions and report medians/distributions rather than a single result.

**Gate:** validated AI inference unchanged or intentionally improved; no permanent driver/CUDA breakage; no misleading benchmark comparisons.

### Phase 6 — Release packaging and maintenance

Deliverables:

- Installer and runtime manifest lockfile; exact hashes and download source records.
- Safe updater that proposes changes, snapshots first, and rolls back on health-test failure.
- Versioned CLI releases and runbooks for troubleshooting, upgrading, uninstalling only project-owned state.
- Release QA checklist, known issues and compatibility matrix.

**Gate:** a second clean test environment can reproduce the configuration with only the official FL Studio installer and documented prerequisites.

---

## 9. Baseline test matrix and measurable targets

| Test | Target | Caveat |
| --- | --- | --- |
| Launch/exit | 20 consecutive runs without failures or orphaned critical processes | Manual app validation may be necessary |
| Save/reopen | Test project structure and plugin state retained | Never touch private projects by default |
| WAV export | File created and playable; compare to expected reference | Bit-identical audio is not always possible |
| Long session | 4 hours without crash or audible underruns | 30-minute early milestone first |
| Audio buffers | Test 1024, 512, 256, optionally 128 frames at 48 kHz | Only call a buffer “stable” after testing |
| VST | Explicit matrix of installed plugin versions | Some vendor DRM may be unsupported |
| Rollback | Restore previous prefix state after simulated failed update | Must preserve project files |
| AI inference | Run a pinned reproducible model with known backend | User must supply model path |
| Diagnostics | Capture failure cause without leaking secrets | Sanitize output and inspect before sharing |

Important: **latency** includes device, scheduling, audio stack, and conversion costs; `buffer_frames / sample_rate` is only the nominal duration of one buffer, **not** round-trip latency. For meaningful Windows comparisons, use the same audio interface, sample rate, buffer, project, plugins, and measurement method.

---

## 10. Agent operating policy: limits, changes, and security

Treat these as **hard constraints**.

1. **Host is production infrastructure.** Inspect first; do not experiment on host-wide packages just to see what happens.
2. **No destructive actions without explicit approval:** no formatting, repartitioning, bootloader changes, `rm -rf` on unmanaged paths, cleaning shared Docker images, modifying system repositories, driver swaps, or OS upgrades.
3. **No unapproved privilege elevation:** commands requiring `sudo` must first be listed with purpose, effects, rollback, and verification. Wait for human execution/approval.
4. **No unapproved downloads/installations:** download only from reputable official/upstream releases and verify hashes or signatures when provided. Do not execute `curl | bash` or unrelated setup scripts.
5. **Protect credentials:** never read or exfiltrate Image-Line/iLok auth tokens, browser profiles, SSH keys, cloud API keys, personal projects or samples. Redact any accidental exposure.
6. **Bounded parallelism:** at most **2 concurrent coding subagents**; at most **one heavy compilation job** at a time; cap build parallelism to **min(8, floor(logical CPUs/2))** until memory/disk headroom is measured. Re-check RAM/swap and filesystem before large builds.
7. **Treat multi-GPU/inference tests as scheduled workloads:** stop or isolate inference while running real-time audio performance tests unless doing a documented contention experiment.
8. **Don't patch third-party code blindly.** Pin commit, make patch reversible, add provenance, and record why upstream behavior is insufficient.
9. **Avoid wishful conclusions:** label every observation `verified`, `inferred`, `hypothesis`, `not tested`, or `blocked`.
10. **Prefer small PR-sized commits** and run tests after each substantive change. Never claim a command worked unless its exit status and output were observed.
11. **Do not overwrite existing config** without backup, diff, and approval. No edits to `~/.bashrc`, `~/.profile`, `/etc/security/limits.conf`, kernel boot parameters, or PipeWire system config as a first pass.
12. **Respect licensing:** no DRM circumvention, patched license servers, pirated plugins, unsigned replacements, or redistribution of Windows binaries.

---

## 11. Suggested read-only host checks

These are *examples for the agent to adapt*, not evidence they have run. Gracefully handle absent commands.

```bash
cat /etc/os-release
cat /etc/linuxmint/info 2>/dev/null || true
uname -a
printf 'session=%s\n' "${XDG_SESSION_TYPE:-unknown}"
lscpu
free -h
df -h "$HOME"
df -i "$HOME"
command -v nvidia-smi && nvidia-smi || true
command -v nvcc && nvcc --version || true
command -v pipewire && pipewire --version || true
command -v wpctl && wpctl status || true
command -v pactl && pactl info || true
command -v wine && wine --version || true
command -v flatpak && flatpak list --app || true
command -v docker && docker --version || true
```

Do not run a giant one-line script that hides failure. Record each probe's exit code and relevant sanitized output. Never scan all of `$HOME` recursively for installers or `.flp` files.

---

## 12. Coding conventions and test expectations

- Python: `>=3.12` if available; avoid installing a different global Python. If host lacks it, document options before requiring changes.
- Tests: `pytest` with subprocess outputs mocked; include tests for missing commands, weird version strings, unsupported distros, path spaces, invalid installer, and malformed manifest.
- Use subprocess with **argument arrays**, not shell interpolation; ensure no command injection via installer path or profile name.
- Treat paths robustly: filenames may contain spaces, Unicode, symlinks. Reject path traversal when writing managed state.
- Use typed dataclasses or small validated schemas for host facts and manifests. Keep secrets out of exception messages.
- Use atomic writes for manifests, snapshots metadata, and reports.
- Make `doctor`, `plan`, and `--dry-run` safely repeatable.
- Pin runtime downloads by exact version and checksum, with a separate manual review step for upgrades.
- CI should test pure Python code; GUI/Wine/audio/CUDA tests are integration tests marked optional and run locally when supported.
- If no reliable automated GUI hooks exist, make an explicit **human test checklist** rather than pretending GUI interactions succeeded.

---

## 13. Immediate OpenCode work order (execute this now)

**Primary task:** Complete **Phase 0 and the non-destructive portion of Phase 1 only**. Do not install FL Studio, Wine, Bottles, audio bridges, CUDA, drivers, or modify system configuration during this first pass.

1. Inspect this repository and the actual host. If no code exists, scaffold the structure in Section 6.
2. Create project `AGENTS.md` summarizing Section 10 with testing commands and referencing `HANDOFF.md`.
3. Implement `python -m flmint doctor --format text|json`; build a safe probe abstraction with subprocess timeouts and graceful absence handling.
4. Implement the installer file validator and SHA-256 calculator without executing the installer.
5. Implement manifest examples and a side-effect-free `flmint plan` or `python -m flmint plan` for stable and experimental profiles, including PipeWire version gate.
6. Create tests and run them, recording exact command, exit status, and summary.
7. Verify the relevant upstream links/dependencies and document findings; record version/commit candidates without installing them.
8. Write `docs/os-migration-decision.md` based on the actual host facts, explicitly explaining whether Mint 22.3 is blocking PipeASIO and whether Xubuntu 26.04 would fix the specific blocker.
9. Update `README.md` with what currently works, what is implemented but not tested on real hardware, and what requires approval.
10. Produce **`reports/phase-0-summary.md`** with concrete output, risks, blocked prerequisites, and the *single next recommended actionable milestone*.

### First-pass acceptance criteria

- [ ] Repository has clear `README.md`, `HANDOFF.md`, `AGENTS.md`, and tested CLI skeleton.
- [ ] `doctor` runs without root privileges and without changing the host.
- [ ] `doctor --format json` emits parseable JSON even when optional commands are missing.
- [ ] `plan` and `install --dry-run` do not create prefixes, install packages, or download anything.
- [ ] Official installer path may be absent without causing crashes.
- [ ] Unit tests cover success, no NVIDIA GPU, missing PipeWire, outdated PipeWire, malformed installer, and unsupported host cases.
- [ ] The work summary distinguishes confirmed observations from assumptions and outlines approvals required to proceed.

### Definition of "done" for the first OpenCode session

Do not stop at a plan. Commit or leave complete implementation files in the repository, execute tests, and report actual results. If host access is unavailable, use mocked tests and clearly label the missing hardware validation. If a privileged action is necessary, **stop at an approval boundary**, document the exact command, and continue productive safe work in the meantime.

---

## 14. OpenCode entry prompt

From the project repository, open OpenCode and give it the following prompt (paste verbatim):

> Read `HANDOFF.md` in full and treat Section 10 as non-negotiable safety policy. Execute Section 13 now: implement Phase 0 plus the non-destructive parts of Phase 1. Start with a read-only host audit and repo inspection. Make actual code, tests, docs, and `AGENTS.md`; do not install or change system-wide software, do not migrate the OS, and do not assume the Windows FL Studio installer exists. Limit heavy builds and parallel agents. Run the unit tests, record results, and finish with `reports/phase-0-summary.md` containing verified facts, blockers, and the next human approval required. Do not claim untested audio/FL Studio functionality works.

```bash
# Starting from a new project directory
mkdir -p ~/src/flmint
cd ~/src/flmint
# Copy this file into the repository as HANDOFF.md
opencode
```

**Note:** The agent must create `AGENTS.md` during the first session because OpenCode automatically loads repository-level instructions from `AGENTS.md`. This handoff is detailed context; it is not a substitute for the agent policy file.

---

## 15. Handoff caveats / unresolved inputs

- No FL Studio installer has been supplied to this handoff. User must provide the official `.exe` path for Phase 2.
- Actual host distro and audio device must be probed.
- GPU/driver/CUDA details must be probed even if earlier project discussions mention an RTX 3090.
- Performance targets are **acceptance targets**, not existing measurements.
- Wine, FL Studio, PipeASIO, and OpenCode change rapidly; lock tested versions rather than using “latest” indiscriminately.
- A custom Wine build with compatibility patches may improve plugin behavior but is higher maintenance; it belongs in the experimental track until reproducibility is demonstrated.
- FL Studio on Linux remains an unofficial configuration and should have a documented Windows fallback for critical projects.

**Starting instruction:** implement the host audit and safe CLI scaffold first. Do not confuse a comprehensive to-do list with a working DAW.

---

## 16. Session status update (2026-11-03)

**Overall status:** Phase 0 and the non-destructive Phase 1 slice are implemented and locally validated. No FL Studio installer, Wine/Bottles, PipeASIO, WineASIO, CUDA package, driver, or OS change was executed. Host-changing Phase 2 remains blocked pending human approval, exact artifact pinning, and official checksum/provenance review.

### Section 13 work-order status

- [x] Inspected the repository and actual host without privilege escalation.
- [x] `AGENTS.md` exists and references this `HANDOFF.md`.
- [x] Implemented `python -m flmint doctor --format text|json` with safe probes, timeouts, and graceful absence handling.
- [x] Implemented installer validation and streaming SHA-256 without executing the installer.
- [x] Implemented stable/experimental profile planning and the PipeWire PipeASIO gate.
- [x] Created and ran unit tests; exact prior result recorded below.
- [~] Verified relevant upstream links and recorded candidates, but final `docs/upstream-research.md` is still pending.
- [ ] `docs/os-migration-decision.md` still pending.
- [ ] README/docs refresh still pending beyond the current quickstart.
- [ ] `reports/phase-0-summary.md` still pending.

### Completed tasks

- Scaffolded the `flmint` package under `src/flmint/`, including `doctor`, `plan`, installer validation, profile loading, planning, state safety, runtime candidate registry, and Phase 2+ refusal stubs.
- Added profile examples:
  - `profiles/stable.example.yaml`
  - `profiles/experimental.example.yaml`
- Added CLI commands:
  - `python3 -m flmint doctor --format text|json`
  - `python3 -m flmint doctor --format json --save reports/host-audit.json`
  - `python3 -m flmint plan --installer PATH --profile stable|experimental`
  - `python3 -m flmint install ... --dry-run`
  - refusal stubs for `launch`, `snapshot`, `diagnose`, and `bench`
- Added test suite files under `tests/`, including CLI, doctor, installer, manifest, planner, probe, state, audio, and Phase-stub coverage.
- Added read-only helper scripts:
  - `scripts/collect_host_facts.sh`
  - `scripts/smoke_test.sh`
- Saved a read-only host audit to `reports/host-audit.json`.
- Saved a non-destructive stable plan to `reports/plan-stable.txt`.
- Recorded upstream candidate versions/checksums without downloading or installing them.
- Recorded community FL-on-Linux warnings as candidate findings, not verified facts for this host.

### Verified host facts

Host audit summary:

- OS: Ubuntu `26.10` (`stonking`), non-LTS warning recorded.
- Kernel: `7.3.0-10-generic`
- Architecture: `x86_64`
- Session/desktop: `x11 / XFCE`
- CPU: AMD Ryzen 7 5700X, `16 logical CPUs / 8 physical cores`
- Memory: total `64219 MiB`, currently available `5794 MiB`
- Disk mount `/`: free `175 GiB`, free inodes `14690041`
- GPU: NVIDIA GeForce RTX 3090, driver `580.178.04`, `24576 MiB` memory
- CUDA toolkit detected: `12.4`
- PipeWire: `1.6.8`, present
- PipeWire Pulse: present
- WirePlumber: present
- Flatpak: `1.18.4`, present
- Docker: absent
- Wine: absent
- Bottles: absent
- Wine prefix at `~/.wine`: absent
- PipeWire PipeASIO gate: `1.6.8 >= 1.4.2`, pass as a gate check only
- Host glibc observed separately: `2.44`

Official installer inventory:

- File: `~/Downloads/flstudio_win64_26.1.7.5654.exe`
- Size bytes: `1106029776`
- SHA-256: `6ddf9f23a8a0d2f9b8b11b77b831fed09231586899faa185e1026cc0eea4edca`
- `flmint` PE report: `x86`
- Warnings recorded:
  - `32-bit PE: FL Studio 26 requires a 64-bit Windows installer`
  - `Authenticode signature not validated locally; cross-check SHA-256 against the Image-Line download page`

No installer was run.

### Tests and quality gates

Previous passing command:

```bash
.venv/bin/python -m pytest && .venv/bin/ruff check src tests && .venv/bin/mypy
```

Previous passing result:

- `54 passed, 13 subtests passed`
- `All checks passed!`
- `Success: no issues found in 17 source files`

Real read-only commands run:

```bash
scripts/collect_host_facts.sh
if .venv/bin/python -m flmint plan --installer "$HOME/Downloads/flstudio_win64_26.1.7.5654.exe" --profile stable --format text > reports/plan-stable.txt; then echo exit=0; else echo exit=$?; fi
```

Exit status: `0`.

Read-only glibc check run separately:

```bash
getconf GNU_LIBC_VERSION
```

Result: `glibc 2.44`.

### Upstream candidates recorded without installation

These are candidates, not pinned/tested artifacts:

- Official Image-Line download page:
  - Observed: `Version 26.1.7.5654 · 1.03 GB · Windows 10, 11, or newer`
  - Compatible CPUs observed: Intel and AMD; ARM not supported.
  - No published SHA-256 visible in fetched page.
- PipeASIO:
  - Candidate release: `v1.10.0`
  - Candidate x86_64 asset: `pipeasio-v1.10.0-archlinux-x86_64.tar.gz`
  - Release JSON SHA-256: `54f959381e1a60f05d0e3b662ed09b08d444d3161a248cd9964c23f47b057a5b`
  - Minimum PipeWire: `1.4.2`
  - Minimum glibc: `2.38`
  - Wine SDK shown: `wine-11.18`
  - Host PipeWire passes the version gate; host glibc exceeds the minimum.
  - Compatibility with Bottles Flatpak remains a concern from release-page warnings and must be reviewed before use.
- DawGeProton:
  - Candidate tag: `DAW-GE-Proton11-6c`
  - Candidate tar.gz size: `553597099`
  - GitHub asset digest: `aecf59518c1137028f6c47afc8e497064d6c5d0f206df6ea6d385dd0766f02d5`
  - Also published: `DAW-GE-Proton11-6c.sha512sum`
  - Not downloaded, not installed, not runtime-tested.
- WineASIO:
  - Candidate release: `v1.3.0`
  - Candidate source tar.gz size: `102542`
  - GitHub asset digest: `f8bf74c871233f65e5befecc7b4f2629f2566f84e951e363af0ad51eae516a4c`
  - License noted in profile example: `GPL-2.0-or-later`
- Bottles:
  - Flathub candidate: `com.usebottles.bottles`, observed version `67.5`
  - Bottles Flatpak observed/app size: `171 MiB`
  - Bottles is not installed on the audited host.
- Wine:
  - Candidate version remains unpinned.
  - `https://www.winehq.org/news/` returned HTTP `403`.
  - Wine GitLab MR `11824` could not be verified because GitLab returned an Anubis bot challenge.

Community guide candidate findings:

- Source: `https://github.com/Torbuntu/fl-studio-linux-setup`
- Claimed issue: FL Studio `26.1.4` has a new certificate that breaks Wine WinTrust with `WINTRUST_DefaultVerify returning 80096004`.
- Claimed workaround: use FL Studio `26.1.3` or lower until Wine applies the fix referenced by Wine GitLab MR `11824`.
- Claimed runner workaround: install `DAW-GE-Proton11-6c` into a custom Bottles runner directory, including Flatpak Bottles runner path examples.
- Additional warning: FL Cloud Plugins may have a memory leak.
- These are unofficial community claims, not verified host results.

### Current unverified boundaries

- FL Studio compatibility is not verified.
- FL Studio install/launch/activation is not verified.
- FL Studio project save/reopen is not verified.
- Offline export is not verified.
- ASIO, PipeASIO, WineASIO, JACK, XRUN, round-trip latency, record/monitor behavior, plugin behavior, GUI behavior, WebView2/login behavior, GPU performance, AI coexistence performance, and benchmarks are not verified.
- Official installer checksum is not matched against a published Image-Line checksum.
- The local installer PE result `x86` is recorded as a warning, not adjudicated.
- Bottles Flatpak versus PipeASIO compatibility is not resolved.
- Component checksum digests from upstream metadata are recorded as candidates, not as verified local artifacts.

### Blocked next steps requiring human approval

- Human review/approval required before any download, Flatpak install, runner install, prefix creation, Wine/Proton execution, installer execution, activation, or benchmark.
- Obtain/confirm official FL installer checksum or signed provenance from Image-Line.
- Decide whether local installer `pe_arch: x86` is a parser warning on the installer stub or a real blocker.
- Decide whether to keep current official installer `26.1.7.5654` or seek a known-working older installer provenance because of the community WinTrust `26.1.4+` warning.
- Resolve PipeASIO manager versus Bottles Flatpak compatibility before experimental audio work.
- Pin selected candidate versions and checksums in profiles after review.
- Implement snapshots before any Phase 2 prefix mutation.

### Single next recommended actionable milestone

**Human-review the candidate pin set and official installer provenance only; do not install yet.** Specifically: review `reports/plan-stable.txt`, approve/reject the recorded candidate versions/checksums, obtain the official Image-Line checksum or signed installer provenance, then rerun a dry-run plan with reviewed pins before any Phase 2 prefix/install step.

---

## 17. Session status update (2026-11-03, session 2)

**Overall status:** Phase 0 and the non-destructive Phase 1 slice are now **complete**, including the
docs and reports that were pending in section 16. Snapshots are implemented (unit-verified) so the Phase 2
safety prerequisite exists. Phase 2 itself is still **not started**: no download, install, prefix, runner,
audio bridge, driver, kernel, PipeWire, or OS change occurred.

### Section 13 work-order status (now closed)

- [x] Items 1-6 (repo/host inspection, `AGENTS.md`, `doctor`, installer validator, planning + PipeWire gate, tests).
- [x] Item 7 `docs/upstream-research.md` written (was `[~]` in section 16).
- [x] Item 8 `docs/os-migration-decision.md` written from measured host facts.
- [x] Item 9 `README.md` refreshed with works / implemented-but-untested-on-hardware / approval-required.
- [x] Item 10 `reports/phase-0-summary.md` produced with blockers and the single next milestone.
- [x] First-pass acceptance criteria re-verified (see section 17 "Quality gates" below).

### Code changes this session

- `src/flmint/snapshots.py`: replaced the stub with a working module — `create_snapshot`,
  `list_snapshots`, `restore_snapshot`, managed XDG-aware paths
  (`~/.local/share/flmint/profiles/<profile>/{prefix,snapshots}`), single-component name/profile
  validation, no-overwrite policy, disk headroom check (~1.2x + 256 MiB), verified SHA-256 before
  restore, staging extraction with `filter="tar"` and single-`prefix`-tree layout enforcement,
  previous prefix preserved as `prefix.discarded-<stamp>`, missing archives reported not deleted.
- `src/flmint/errors.py` + `src/flmint/__init__.py`: added/exported `SnapshotError`.
- `src/flmint/installer.py`: NSIS engine detection (`installer_engine: nsis`, 2 MiB scan window,
  `Nullsoft`/`NSIS` markers) and warning wording that explains a 32-bit **installer stub** is expected.
  This closes the section 16 open item "is `pe_arch: x86` a parser warning or a real blocker".
- `src/flmint/cli.py`: `snapshot create|list|restore` wired to real renderers; `launch`, `diagnose`,
  `bench` remain intentional refusals. `snapshot list` on this host exits 0; `snapshot create` exits 2
  with `no prefix to snapshot`.
- `src/flmint/installer_runner.py`: unchanged in intent — `perform_install()` still raises
  `ApprovalRequiredError`; there is no code path that creates a prefix.
- `src/flmint/planner.py`: snapshot step note now states the module is implemented/tested but gated on
  prefix creation.
- `profiles/stable.example.yaml`, `profiles/experimental.example.yaml`: Bottles license corrected to
  `GPL-3.0-only` (Flathub verified); notes now record verified candidate versions/digests and the
  upstream PipeASIO prerequisites plus the Flatpak-unsupported constraint. Versions remain `null` on purpose.
- Tests: `tests/test_snapshots.py` (new), snapshot CLI cases in `tests/test_cli.py` (XDG `XDG_DATA_HOME`
  isolation), NSIS installer case in `tests/test_installer.py`, snapshots removed from
  `tests/test_phase_stubs.py`.

### Quality gates (exact, this session)

```bash
.venv/bin/python -m pytest      # 69 passed, 14 subtests passed in 0.13s      exit 0
.venv/bin/ruff check src tests  # All checks passed!                          exit 0
.venv/bin/mypy                  # Success: no issues found in 17 source files exit 0
```

First-pass acceptance criteria check:

- [x] `README.md`, `HANDOFF.md`, `AGENTS.md`, tested CLI skeleton present.
- [x] `doctor` runs non-root and mutates nothing (`~/.local/share/flmint` confirmed absent afterwards).
- [x] `doctor --format json` parses even with absent optional tools (mocked-probe tests + real run).
- [x] `plan` and `install --dry-run` create no prefixes/packages/downloads.
- [x] Absent installer path is handled without crashing (tested and real-host run without `--installer`).
- [x] Unit tests cover success, no-NVIDIA, missing/outdated PipeWire, malformed installer, unsupported host.
- [x] Summaries separate confirmed observations from assumptions and list required approvals.

### Verified host facts (added this session)

- Host is **not** Linux Mint: `/etc/linuxmint/info` absent. glibc `2.44`. Memory available at audit time
  `9536 MiB` of `64219 MiB`. Disk `/` free `175 GiB`, inodes free `14689732`.
- Default PipeWire sink is the Focusrite **Scarlett Solo USB** (Headphones / Line 1-2); Mic1/Mic2 sources
  present. `pw-dump`, `pw-cli`, `wpctl`, `nvidia-smi`, `mpstat`, `perf`, `glxinfo`, `lspci` present.
  `pw-monjack`, `jackd`, `qjackctl`, `nvtop`, `vulkaninfo`, Docker absent; `ulimit -r` = `0`.
- `~/.wine`, `~/.var/app`, and all `flmint` managed state directories remain absent.

### Corrections to section 16 records

- `pe_arch: x86` is **adjudicated**: NSIS installer stub (markers at offset ~66956), not a 32-bit payload
  signal. Payload architecture is still untested.
- Section 16 listed `54f959381e1a60f05d0e3b662ed09b08d444d3161a248cd9964c23f47b057a5b` as the PipeASIO
  "Release JSON SHA-256"; that digest belongs to `pipeasio-v1.10.0-archlinux-x86_64.tar.gz`.
  `pipeasio-release.json` is `76d4ba4ced26052478f05c1cf9a37bfb75352b3cc1a34795dd4783d56cf702dc`.
- New verified constraint: PipeASIO v1.10.0 release notes state Flatpak is unsupported (Steam **and
  Bottles**), so the section 16 concern about Bottles-vs-PipeASIO is resolved as *architecturally
  incompatible* rather than "needs review".

### Reports and docs now on disk

- `reports/host-audit.json`, `reports/plan-stable.txt`, `reports/plan-experimental.txt`,
  `reports/install-dry-run-stable.txt`, `reports/upstream-candidates.json`, `reports/phase-0-summary.md`.
- `docs/architecture.md`, `docs/rollback.md`, `docs/runbook.md`, `docs/upstream-research.md`,
  `docs/os-migration-decision.md`, `docs/compatibility-matrix.md`, `docs/benchmarks.md`.
- `docs/plan.md` (forward execution plan: blocking decisions D1-D4, Phase 2-6 task order, safe backlog) and
  `CLAUDE.md` (Claude Code mirror of `AGENTS.md`; keep both in sync). README links both.

### Current unverified boundaries (updated)

- FL Studio install/launch/activation/save/reopen/export: unverified (nothing has run).
- WinTrust behavior for 26.1.7.5654 under a pinned runner: unverified; upstream fix status unreadable.
- Snapshot behavior against a **real Wine prefix** (symlinks, sockets, modes, tar round-trip fidelity): unverified.
- PipeASIO/WineASIO registration, XRUN, latency, plugin behavior, GUI behavior, GPU behavior, AI
  coexistence: unverified.
- DAW-GE-Proton archive **contents** and its usability as a runner: unverified (digest verified only).

### Blocked next steps requiring human approval (unchanged in kind, clarified)

1. Pin exact versions + SHA-256s into `profiles/*.yaml` after review.
2. Choose the runner architecture: Flatpak Bottles (PipeASIO unsupported) vs native Wine prefix (PipeASIO-capable).
3. Accept 26.1.7.5654 provenance as-is, or decide on an older official installer path for the WinTrust claim.
4. Approve any download/extract/build/prefix creation/installer execution/activation, one step at a time.
5. Provide a legitimately unlocked license for save/reopen acceptance, and a user-owned model if the AI track is wanted.

### Single next recommended actionable milestone

**Human pin/architecture review only — no installation.** Answer: which runner architecture, which exact
versions + digests get pinned, and whether 26.1.7.5654 is accepted. Then rerun `plan` + `install --dry-run`
with pins in place, and request approval for prefix creation with a baseline snapshot taken immediately
after. Full detail in `reports/phase-0-summary.md`.
## 18. Session status update (2026-11-03, session 3: approvals 1-2 executed, 2.3 blocked)

### What was approved and executed

- Approvals granted: pinned plan sign-off, runner fetch (`DAW-GE-Proton11-6c`), isolated prefix + baseline
  snapshot. Recorded in `reports/decisions.md` ("Approvals already granted and executed").
- **Executed 2.2**: `flmint fetch --profile stable --component daw-ge-proton --approve --extract`
  (1m40s). `553597099` bytes, SHA-256 `aecf5951…f02d5` — exactly the D2 pin; SHA-512 recorded. Stored at
  `~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c.tar.gz`, extracted (safe `tarfile` filter `data`) to
  `~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c` (1.5 GB). Provenance:
  `reports/provenance-daw-ge-proton.json` (`status: verified`, signed CDN redirect query stripped).
- `flmint verify --profile stable --component daw-ge-proton` re-hashes the stored file with no network and
  rewrites the provenance record.

### New measured runner facts (replaces the section 17 "digest verified only" boundary)

- Bundled Wine measured: **`wine-11.0 (Staging)`**; `files/bin/` has only `wine`, `wineserver`, `msidb`,
  `xrandr` (no `wine64`/`wine32`); `files/lib/wine/` carries both `i386-*` and `x86_64-*` trees plus
  `dxvk`, `d7vk`, `vkd3d-proton`, `nvapi`; `files/share/wine/` already ships `gecko` + `mono`;
  `proton` script sets `CURRENT_PREFIX_VERSION="GE-Proton11-6"`.
- The tarball has a top-level directory of the same name, so the effective runner root is
  `~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c/DAW-GE-Proton11-6c`.
- Consequence: PipeASIO builds against `wine-11.18` while the pinned runner ships `wine-11.0` → PipeASIO
  compatibility is `unverified`, and WinTrust behavior is still `not tested`.

### 2.3 blocked: new decision gate D5 (host 32-bit loader)

Every prefix-creation attempt with `WINEPREFIX` set failed identically with `/lib/ld-linux.so.2: could not
open` (exit 1): `wineboot -u`, `WINEARCH=win64 wineboot -u`, `wineboot -u -w win64`, running
`files/lib/wine/x86_64-windows/cmd.exe` directly, and the same with `LD_LIBRARY_PATH` pointed at the runner's
bundled `i386-linux-gnu`. Host: `/lib/ld-linux.so.2` absent, `ldconfig -p` lists only
`ld-linux-x86-64.so.2`, no foreign dpkg architectures, `libc6-i386` not installed (candidate
`2.44-1ubuntu2`), `docker`/`podman`/`distrobox`/`steam` absent, `flatpak 1.18.4` present and unused. Options
(a) `sudo apt install libc6-i386` (recommended, reversible), (b) container runner, (c) re-pin to a
64-bit-only Wine, (d) stop Phase 2 — full table in `reports/decisions.md` D5 and
`reports/runner-install-phase2.md`.

### Host state after this session

- New: `~/.local/opt/flmint/daw-ge-proton/` (archive + extraction).
- Still absent: `~/.wine`, `~/.var/app`, `~/.local/share/flmint` (no prefix), `~/.local/state/flmint` (no
  snapshot). No `apt`, no driver/kernel/PipeWire change, no existing-prefix change. Temp probe prefixes under
  `/tmp/opencode/` were removed.

### Code and gates added this session

- `src/flmint/downloads.py`: pinned-artifact fetch with size + SHA-256 enforcement, digest-mismatch
  quarantine (never extracted), `tarfile` `filter="data"` extraction into managed versioned dirs, local
  re-verify (`verify_local`, `outcome_from_local`), provenance records with `sanitize_url` so signed CDN
  redirect URLs are never persisted.
- `src/flmint/manifest.py`: components now accept `download_url` (https only), `asset` (single filename),
  `size_bytes` (positive int), all validated with positional messages.
- `src/flmint/cli.py`: `fetch` (refuses without `--approve`) and `verify` subcommands.
- `src/flmint/planner.py`: prefix creation approval-gated; new warning when a download component is not
  fetchable (missing `asset`/`download_url`); pin warnings extracted into `_pin_warnings`.
- `profiles/stable.yaml`: runner pin extended with `asset`, `download_url`, `size_bytes`.
- New tests: `tests/test_downloads.py` (fetch/digest/size/extraction safety/verify CLI/sanitization),
  extra `tests/test_manifest.py` fetch-key cases.
- Gates: `89 passed, 18 subtests passed`, `All checks passed!` (ruff), `Success: no issues found in 18
  source files` (mypy).

### Single next recommended actionable milestone

**D5 answered 2026-11-03 = option (a) `sudo apt install libc6-i386`, run by the owner personally** (recorded
in `reports/decisions.md`). `flmint` never runs `sudo`/`apt`, and no package is installed yet. Next agent
steps once `/lib/ld-linux.so.2` exists: create the prefix with the nested runner root, take the baseline
snapshot immediately, then the 2.4 supervised installer run. D4 (unlocked license + user-owned model) is
still unanswered.
## 19. Session status update (2026-11-03, session 3b: D5 executed, 2.3 complete)

### Host change granted + executed by the owner (not by flmint)

- D5 option (a): `sudo apt install libc6-i386` run personally by the owner. Measured afterwards:
  `/lib/ld-linux.so.2 -> ../lib32/ld-linux.so.2`, `libc6-i386 2.44-1ubuntu2` (host glibc `2.44`), 1242 i386
  entries in `ldconfig -p`. This is the only system package change in the whole project so far; `flmint` ran
  no `sudo`/`apt`, and no driver/kernel/PipeWire change was made.

### 2.3 prefix creation (approval 3) — done

- `mkdir -p ~/.local/share/flmint/profiles/stable/prefix` (wine refuses a missing `WINEPREFIX` dir), then
  `env -i HOME=$HOME PATH=/usr/bin:/bin WINEPREFIX=<prefix> WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
  <runner>/files/bin/wine wineboot -u` → exit 0 in 9.8 s. `<runner>` is the **nested** root
  `~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c/DAW-GE-Proton11-6c`.
- Prefix facts: 628 MB; `dosdevices/c: -> ../drive_c`, `dosdevices/z: -> /`; `system.reg`, `user.reg`,
  `userdef.reg`, `.update-timestamp`; **wow64** confirmed (`drive_c/windows/system32` **and** `syswow64`,
  `Program Files (x86)`). Sanity run `wine cmd.exe /c ver` → `Microsoft Windows 10.0.19045` (prefix works;
  not an FL Studio test). `~/.wine` still absent.
- Warning recorded honestly: `Wine cannot find the FreeType font library…` — the runner bundles no
  freetype and the host only has the x86_64 build, so GUI font rendering is `not verified`. Fixing it needs
  an approved i386 freetype package or a bundled lib.

### Baseline snapshot — done and independently re-checked

- `flmint snapshot create --profile stable --name baseline` → 169,666,533-byte archive, 2014 prefix entries,
  SHA-256 `b10f9d29a115b0fcacb9f8f1a3ec18a16da5bd0ce5e860af385d8f960d902b4e`; `sha256sum` reproduced it; the
  tar holds a single `prefix/` tree with symlinks preserved. Manifest `baseline.json` sits next to it under
  `~/.local/share/flmint/profiles/stable/snapshots/` (note: snapshots live under `share`, not `state`).
- `not tested`: `snapshot restore` round-trip against this live prefix.

### Doctor gained the two facts that matter for this decision (re-audited)

- `doctor` now reports `i386_loader_present` (`/lib/ld-linux.so.2`) and `managed_runners` (extracted runners
  under `~/.local/opt/flmint`, keyed on `files/bin/wine`), with capabilities `i386_loader_present` +
  `flmint_runner_installed`; the "no Wine/Bottles runtime present" blocker is suppressed when a managed runner
  exists. Post-D5 audit saved as `reports/host-audit-2026-11-03-post-d5.json` (the Phase 0 audit
  `reports/host-audit.json` is preserved unchanged): `managed_runners =
  ["daw-ge-proton/DAW-GE-Proton11-6c/DAW-GE-Proton11-6c"]`, `i386_loader_present: true`,
  `wine_prefix_present: false` (no `~/.wine`), disk free ~174 GiB.
- Added `doctor --compare <audit.json>`: compares material host facts, capabilities and blockers against a
  saved audit, ignores volatile probe logs/generated timestamps, prints a text or JSON comparison and exits
  `1` on material drift. Current host comparison against
  `reports/host-audit-2026-11-03-post-d5.json` reports no material drift (exit 0).
- Gates after this change: `93 passed, 18 subtests passed`, ruff clean, `Success: no issues found in 18
  source files`.

### Plans re-pinned and re-rendered

- `reports/plan-stable-pinned.txt` and `reports/install-dry-run-stable-pinned.txt` regenerated with the
  updated `profiles/stable.yaml` notes; zero unpinned warnings.

### 2.4 first supervised installer attempt and rollback

- Operator approved 2.4 and watched the attempt. `~/Downloads/flstudio_win64_26.1.7.5654.exe` was re-hashed to
  `6ddf9f23a8a0d2f9b8b11b77b831fed09231586899faa185e1026cc0eea4edca` before prefix mutation.
- Snapshot `pre-installer-2026-11-03` was created with SHA-256
  `ada182756264711bf155f8f016f88cd7741a8d488190e5587a7119200e8c4635`, then independently re-hashed.
- The installer was launched with explicit `WINEPREFIX`, managed nested runner root, `env -i`, `WINEDEBUG=-all`,
  `WINEDLLOVERRIDES="mscoree,mshtml="`, and GUI env variables passed explicitly. Measured failure:
  `libgcc_s.so.1 must be installed for pthread_exit to work` plus `wine client error:138: write: Bad file
  descriptor`; no Wine/wineserver processes remained and `~/.wine` stayed absent.
- Operator approved the package-retry path. `flmint` then ran `snapshot restore` against the live prefix,
  verified the archive digest, and preserved the failed-attempt prefix at
  `~/.local/share/flmint/profiles/stable/prefix.discarded-20261103T134414Z` for operator confirmation.

### Single next recommended actionable milestone

**Owner-run package install**: run `sudo apt install lib32gcc-s1` personally. After the operator confirms it is
installed, create/confirm a clean pre-run snapshot path and retry the supervised installer run, recording
WinTrust behavior as a measured outcome only (no pre-emptive workaround). D4 (unlocked Image-Line license path
+ user-owned model) is still unanswered, so 2.5 activation, 2.7 save/reopen + offline WAV export and all of
Phase 5 stay blocked.

## 20. Session status update (2026-11-03, session 3c: 2.4 complete via silent install)

### Host/package changes during the 2.4 retry path

- Owner-run packages were approved/executed as needed: `libc6-i386` (D5), `lib32gcc-s1`, and i386 GUI support
  packages (`libfreetype6:i386`, `libgl1:i386`, `libx11-6:i386`, `libxext6:i386`, `libxrender1:i386`). `flmint`
  ran no `sudo` or `apt`.
- Measured dpkg state now includes foreign architecture `i386`, `/usr/lib32/libgcc_s.so.1` present, and the
  packages listed above installed (`ii`). This removed the original `libgcc_s.so.1` startup failure.

### Interactive installer attempts: measured but unsuccessful

- Multiple supervised interactive attempts used the isolated prefix, pinned installer, explicit `WINEPREFIX`,
  managed runner, and `WINEDEBUG=-all,+wintrust WINEDLLOVERRIDES="mscoree,mshtml="`.
- The installer extracted NSIS payload files (`System.dll`, `UAC.dll`, `UserMgr.dll`, `ILSetup.dll`,
  `InstallOptions.dll`, etc.), but hung with low CPU use. Wine client threads were blocked on `anon_pipe_read`;
  `wineserver` was in `ep_poll`.
- The installer window `FL Studio 2026 Setup` existed but was reported off-screen, not clickable, or fully
  glitched. In virtual-desktop mode (`explorer /desktop=flstudio_installer,1920x1080`) the desktop appeared but
  the installer still did not become reliably interactive.
- Every failed/hung attempt was killed, verified clean with `ps`, and restored from its pre-run snapshot.
  Rollback copies remain pending operator deletion.

### 2.4 successful silent install

- Pre-run snapshot: `pre-installer-silent-2026-11-03`
  (`fe26437003557f66534bb9c338771a86ac84b40467c79fd55b2577b160a5b60f`).
- Successful command pattern:
  ```bash
  env -i HOME=$HOME PATH=/usr/bin:/bin DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY LANG=C.UTF-8 \
    WINEPREFIX=$HOME/.local/share/flmint/profiles/stable/prefix \
    WINEDEBUG=-all,+wintrust WINEDLLOVERRIDES="mscoree,mshtml=" __COMPAT_LAYER=RunAsInvoker \
    ~/.local/opt/flmint/daw-ge-proton/DAW-GE-Proton11-6c/DAW-GE-Proton11-6c/files/bin/wine \
    ~/Downloads/flstudio_win64_26.1.7.5654.exe /S
  ```
- Measured results:
  - log `2026-11-03-flstudio-installer-silent.log`:
    `wineserver: using server-side synchronization.` plus successful `regsvr32` of
    `C:\Program Files\Image-Line\FL Studio ASIO\ILWASAPI2ASIO_x64.dll`.
  - no WinTrust/certificate error text observed under `WINEDEBUG=-all,+wintrust`.
  - installer/Wine/wineserver processes disappeared after roughly 3 minutes; no orphan processes remained.
  - installed prefix measured at 31,027 files / 3,759,034,292 bytes.
  - `FL Studio 2026` installed under `drive_c/Program Files/Image-Line/FL Studio 2026` with `FL64.exe`,
    `FL64 (scaled).exe`, `FLEngine_x64.dll`, `uninstall.exe`, plugin/data directories.
  - Image-Line registry paths written under `HKCU` and `HKLM` point to `FL64.exe` and `FLEngine_x64.dll`.
  - bundled VC++ redist log exits `0x0`.
  - post-install snapshot `post-installer-silent-2026-11-03` captured the installed prefix
    (`06c664c9…c6c8`, 32,850 entries / 4,841,487,814 bytes).
  - `doctor --compare reports/host-audit-2026-11-03-post-d5.json` reported no material host/capability drift;
    current JSON audit saved as `reports/host-audit-2026-11-03-post-installer.json`.

### Current milestone

- **2.4 is complete as a silent install**. The interactive installer UI remains unverified and glitch-prone on
  this runner/host combination.
- **Do not claim FL Studio launch/activation works**. `FL64.exe` is present, but UI launch, licensing UI, audio
  device selection, plugin enumeration, save/reopen, WAV export, and orphan-free repeated launch behavior are
  `not tested`.
- Next required human decision is still **D4**: unlocked Image-Line license path + user-owned model. Before
  activation/launch validation, an explicit approval is also required for supervised `FL64.exe` launch.

## 18. Session status update (2026-11-03, session 3 - supervised launch/auth and PipeASIO registration)

### Supervised launch and manual authentication

- Owner approved a supervised `FL64.exe` launch attempt and manual authentication after the installed-prefix
  state was snapshotted.
- Snapshots exist for the stable prefix:
  - `post-installer-silent-2026-11-03`: `06c664c9e0e1a2e8f9ce8a8d9edbfd4728e63f8e83de239a06a183785b8cc6c8`
  - `pre-launch-attempt-2026-11-03`: `0549c1d0757dfc9474c42578a9105b90f01bb98dfe8882beeba28b19307b6101`
  - `post-launch-attempt-2026-11-03`: `295715ec96dc912a93cc36982552601441b7dacd0d846ec4973409af98aaf151`
  - `pre-manual-auth-2026-11-03`: `bd6ddd0763a3d30215c7ac7e1fdc3eb134b6a61123ca8a16f13413332ac6bfcd`
  - `post-manual-auth-2026-11-03`: `031f2a0fa91752e9943ab2d9d5874929e31f342936b64f7db0073acc1f215814`
- Logs:
  - `~/.local/state/flmint/logs/2026-11-03-flstudio-launch.log`
  - `~/.local/state/flmint/logs/2026-11-03-flstudio-manual-auth-launch.log`
- X windows observed during the manual-auth attempt included `FL Studio 2026`, `Welcome to FL Studio - in trial
  mode`, `FL Studio is in trial mode`, and a MIDI settings window. The operator reported the app was working
  after manual authentication, but full license activation and project save/reopen/WAV export were not measured.
  - Update 2026-11-05: owner reports FL Studio is **no longer in trial mode** (activated). Owner-reported only;
    no activation evidence captured by `flmint`.
- Later process checks showed no remaining `FL64.exe`, Wine, or `wineserver` processes.
- Launch logs contained ALSA errors and underruns:
  - `unable to open slave`
  - `underrun occurred`
- Measured audio config after the launch:
  - PipeWire graph: `clock.rate = 48000`, `clock.quantum = 1024`, `clock.min-quantum = 32`,
    `clock.max-quantum = 2048`, `clock.force-quantum = 0`.
  - FL Studio output registry: `Buffer length (DS) = 4096`, `Sample rate = 44100`, Wine ALSA driver in use.

### PipeASIO online lookup and experimental registration

- Official PipeASIO docs reviewed: `https://m0n7y5.github.io/pipeasio/`.
- PipeASIO v1.10.0 was selected as the likely best low-latency path because it is a native PipeWire ASIO client,
  unlike FL Studio ASIO (through Wine audio) or WineASIO (requires JACK).
- Owner approved a PipeASIO experimental test limited to fetch, digest verification, install/register in an
  isolated experimental prefix, and no PipeWire host config changes.
- Fetched and digest-verified artifacts under `~/.local/share/flmint/cache/pipeasio/v1.10.0/`:
  - `pipeasio-release.json`: `76d4ba4ced26052478f05c1cf9a37bfb75352b3cc1a34795dd4783d56cf702dc`
  - `pipeasio-v1.10.0-archlinux-x86_64.tar.gz`:
    `54f959381e1a60f05d0e3b662ed09b08d444d3161a248cd9964c23f47b057a5b`
- Installed driver to `~/.local/lib/wine` and registered it in:
  - `~/.local/share/flmint/profiles/experimental/prefix`
- Experimental snapshots:
  - `pre-pipeasio-2026-11-03`: `8b865a4c83623f5cce2d6cb58dca25945a50eb0cee4ca8d5edbf72cd567dd166`
  - `post-pipeasio-register-2026-11-03`: `80e46f9229a92f40979eaae98a7b0d3ef62ba3f36207300ed6d53f7899c1e66c`
- Direct runner `regsvr32 /s pipeasio64.dll` succeeded under `wine-11.0 (Staging)` even though the pinned
  PipeASIO prebuilt Arch artifact was built against `wine-11.18`. This is registration success only.
- Registry now contains `HKLM\Software\ASIO\PipeASIO` and `HKCR\CLSID\{2D3CA9E2-1193-4C5D-B5FD-38798F3DC074}`.
- No PipeASIO FL Studio runtime test, node observation, XRUN measurement, or latency measurement had been run at
  registration time. Section 19 records later supervised launch tests.

### Next required approval

Superseded by section 19. The supervised experimental-prefix launch approval was later given and executed.
D4 has since been cleared manually as a decision blocker; activation/save/reopen/export/AI items remain
`not tested` until actually exercised.

## 19. Session status update (2026-11-03, session 4 - PipeASIO launch tests and D4 clearance)

### PipeASIO supervised launch results

- Owner approved supervised FL Studio launch with PipeASIO in the experimental prefix, manual ASIO selection,
  buffer checks, read-only PipeWire/process monitoring, clean close, snapshot, and logs.
- Working launch environment required:
  - `WINEDLLPATH=$HOME/.local/lib/wine`
  - `XDG_RUNTIME_DIR=/run/user/1000`
- Without `XDG_RUNTIME_DIR`, PipeASIO failed with:
  - `[pipeasio] ERR: pw_context_connect failed (is the PipeWire daemon running?)`
- Setting `PIPEWIRE_REMOTE=unix:/run/user/1000/pipewire-0` did not fix the connection; working launches did not
  set `PIPEWIRE_REMOTE` or `PULSE_SERVER`.
- At 512 samples, FL Studio selected PipeASIO and audio played. Saved PipeWire dumps captured a running `FL64`
  PipeASIO node with `force-rate=44100`, `force-quantum=512`, `latency=512/44100`, format `F32P`
  `44100 Hz x2`, and active links to the Scarlett sink. PipeASIO logged one XRUN warning for that activation.
- At 256 samples, the owner requested using the config because 256 could not be changed live.
  `~/.config/pipeasio/config.ini` was set to `buffer_size=256`, `fixed_buffer_size=on`, `sample_rate=0`;
  backup at `~/.config/pipeasio/config.ini.bak-512`. FL Studio was relaunched with `PIPEASIO_DEBUG=1`.
- The 256 run worked well. Debug log startup lines show:
  - `audio_activate: follow_device=0 quantum=256 forced_rate=44100`
  - `latency=256/44100`
  - `our_node_id=102`
  - `4 ports, 256-sample buffers, 44100 Hz`
- Live `pw-dump` showed `FL64` running with `force_rate=44100`, `force_quantum=256`, `latency=256/44100`,
  `driver=68`, and `pipeasio.node=1`. PipeASIO debug process lines continued through cycle `33800` with
  `buffer_size=256 quantum=256 rate=1/44100`. PipeASIO logged exactly one XRUN warning for that activation:
  `[pipeasio] WARN: xrun: missed the cycle deadline (1 this activation, buffer size 256)`.
- Owner stopped after 256 and reported the run worked well. FL Studio was killed cleanly with the pinned runner
  `wineserver -k`; no Wine/FL windows remained.
- Accepted PipeASIO setting for this session: 256 fixed samples, PipeASIO debug backup:
  `~/.config/pipeasio/config.ini.tested-256`.
- No PipeWire host config file or PipeWire metadata setting was changed.

### Snapshot cleanup

- After the successful 256 run, owner requested dropping other snapshots.
- The only experimental PipeASIO snapshot kept is:
  - `post-pipeasio-256-test-2026-11-03`:
    `dbda1d34af46acd9fa97e942483699c9f14d5524402043f2d7c10db2e2d7f13d`
    (1875697529 bytes, 36169 entries, prefix bytes 5013443743)
- Deleted experimental snapshots: `pre-pipeasio-2026-11-03`,
  `post-pipeasio-register-2026-11-03`, `pre-pipeasio-launch-2026-11-03`,
  `post-pipeasio-selection-failed-2026-11-03`, and `post-pipeasio-512-success-2026-11-03`.
- Logs remain as evidence, but deleted snapshot archives are no longer available for rollback.

### D4 status

- Owner manually cleared D4 in-session. `flmint` recorded this in `reports/decisions.md` as a decision unblock,
  not as evidence that activation, save/reopen, WAV export, or Phase 5 AI behavior works.
- Do not claim full activation/license validation, project save/reopen, WAV export, formal latency benchmarking,
  plugin behavior, recording/monitoring, or GPU/AI coexistence is verified until actually tested.
