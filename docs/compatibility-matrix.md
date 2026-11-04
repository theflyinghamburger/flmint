# Compatibility matrix (living document)

Rules for this table:
- `verified` = measured on this host or read from a primary upstream source this session.
- `unverified` = upstream/community claim not reproduced here.
- `not tested` = the capability exists in theory, no FL Studio run has occurred yet.
- `blocked` = cannot proceed without a human decision/approval or a blocked source.
- Nothing in this file claims FL Studio works. No FL Studio binary has been executed on this host.

## Host gates (Phase 0, measured)

| Gate | Requirement | Measured | Result |
| --- | --- | --- | --- |
| Distribution | any supported Ubuntu | Ubuntu 26.10 (interim, EOL Jul 2027) | `verified` — usable for experiments, not LTS |
| CPU architecture | x86_64, Intel/AMD | AMD Ryzen 7 5700X, 8c/16t | `verified` |
| Memory | enough for Wine + FL Studio + headroom | 64219 MiB total | `verified` |
| Disk headroom | ≥ 12288 MiB (stable profile) | 175 GiB free on `/` | `verified` |
| PipeWire (PipeASIO prereq) | ≥ 1.4.2 | 1.6.8-1ubuntu4 | `verified` **gate pass only**, not a runtime test |
| glibc (PipeASIO prereq) | ≥ 2.38 | 2.44 | `verified` gate pass only |
| GPU/driver | NVIDIA working | RTX 3090, 580.178.04 (`nvidia-driver-580-open`) | `verified` |
| CUDA toolkit | for the AI coexistence track | 12.4 | `verified` presence only |
| Audio interface | consistent device for comparisons | Focusrite Scarlett Solo USB (default PipeWire sink) | `verified` |
| JACK | required by the WineASIO fallback | `jackd` absent, `ulimit -r` = 0 | `verified` — fallback needs approved installs |
| Flatpak | needed for the Bottles track | 1.18.4 present, no apps installed | `verified` |
| Wine / Wine prefix | Phase 2 prerequisite | absent | `verified` — Phase 2 blocked |
| Docker | optional AI track | absent | `verified` |
| Official installer present | Phase 2 prerequisite | `~/Downloads/flstudio_win64_26.1.7.5654.exe` | `verified` |
| Installer architecture | 64-bit FL Studio payload | installer stub is PE32/NSIS (expected) | `verified` for the stub; payload `not tested` |
| Installer provenance | published checksum match | no Image-Line SHA-256 published | `blocked` |

## Runtime candidates (Phase 2/3, unpinned by policy)

| Component | Candidate | Digest | Status |
| --- | --- | --- | --- |
| Bottles (Flathub) | 67.5 | not pinned | `verified` metadata; **removed from stable profile**; not installed; license GPL-3.0-only |
| DAW-GE-Proton | `DAW-GE-Proton11-6c` | `aecf5951…f02d5` recorded | `verified` upstream digest; **downloaded, extracted, run**; bundled Wine measured as `wine-11.0 (Staging)` |
| PipeASIO | v1.10.0 | Arch tarball `54f95938…7a5b` measured; installed Arch artifact selected | `verified` installed + registered in experimental prefix; `partial` FL list/select/audio startup at 512 and 256; formal latency/XRUN benchmark untested; Flatpak prefixes unsupported upstream |
| WineASIO | v1.3.0 | `f8bf74c8…6a4c` recorded (prior session) | `unverified` this session; needs JACK (absent) |
| Wine (standalone) | none | — | `blocked`: version not resolvable from here (403 / bot challenge) |

## FL Studio behavior rows (Phase 2+, all currently `not tested`)

| Row | Test target | Current status |
| --- | --- | --- |
| Installer completes inside an isolated prefix | official installer, pinned runner | `partial`: supervised silent `/S` install completed; interactive UI behavior unverified |
| WinTrust / certificate handling on `26.1.7.5654` | documented as broken for `26.1.4+` by community | `unverified` risk; `blocked` upstream status check |
| Legitimate activation (own Image-Line account) | no license bypass | `not tested` |
| WebView2 / embedded login behavior | documented failure modes | `not tested`; FL Cloud excluded from acceptance |
| Launch/exit stability | 20 consecutive runs, no orphaned critical processes | `partial`: supervised windows/log launches observed and clean kills recorded; 20-run gate not tested |
| Save/reopen `.flp` | test project + plugin state retained | `not tested`; official **trial cannot reopen saved projects** (`verified` official page) |
| Offline WAV export | playable file, compared to a reference | `not tested` |
| Long session | 30-minute milestone, then 4 hours | `not tested` |
| Built-in ASIO / Wine audio baseline | 1024/512/256 frames @ 48 kHz | `not tested` |
| PipeASIO bridge | registration + XRUN/latency measurement | `partial`: registered, FL Studio selected PipeASIO, audio startup observed at 512 and 256, one logged XRUN warning per activation; formal XRUN/latency benchmark not tested, Flatpak constraint retained |
| WineASIO/JACK bridge | comparison path | `not tested`, needs approved JACK install |
| VST2/VST3 plugin matrix | per-plugin vendor/version/result | `not tested`; no plugin inventory collected yet |
| GUI rendering (Direct2D/Direct3D paths) | documented toggle per prefix | `not tested` |
| Prefix rollback | `flmint snapshot restore` after simulated failure | module `implemented` + unit-tested; **prefix-level restore `not tested`** |
| GPU-heavy FL Studio plugin load | RTX 3090 behavior | `not tested` |
| AI workload coexistence (`llama.cpp` on user-supplied model) | measured medians/distributions | `not tested`; model not supplied yet |

## Known constraints that shape the matrix

- **PipeASIO × Flatpak**: upstream release notes state Flatpak (Steam and Bottles) is unsupported.
  A PipeASIO experiment therefore implies a non-Flatpak Wine runtime, which changes what
  "stable profile" means. This must be decided before Phase 3.
- **FL Studio trial vs license**: save/reopen acceptance cannot be validated with the trial.
- **Latency wording**: `buffer_frames / sample_rate` is a buffer duration, **not** round-trip
  latency; no latency number may be reported without loopback measurement on the Scarlett Solo.
- **Distro churn**: 26.10 loses standard maintenance in Jul 2027, so any long-lived matrix entry
  must eventually be re-verified on a pinned LTS base.
