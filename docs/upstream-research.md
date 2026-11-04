# Upstream research log (read-only)

`flmint` records upstream facts here before anything is pinned, downloaded, built, or run.
Every line is labeled `verified`, `unverified`, `hypothesis`, `not tested`, or `blocked`.
Machine-readable copy: `reports/upstream-candidates.json` (gitignored).

Last research pass: 2026-11-03 (HTTPS metadata only; no artifact was downloaded or executed).

## 1. Official FL Studio installer

| Item | Value | Status |
| --- | --- | --- |
| Local file | `~/Downloads/flstudio_win64_26.1.7.5654.exe` | verified |
| Size | 1,106,029,776 bytes | verified |
| SHA-256 | `6ddf9f23a8a0d2f9b8b11b77b831fed09231586899faa185e1026cc0eea4edca` | verified (recomputed locally, matches prior session) |
| PE machine | `0x014C` (i386), magic `0x10B` (PE32), subsystem GUI, 5 sections | verified |
| Installer engine | NSIS (`Nullsoft`/`NSIS` markers at offset ~66956) | verified |
| Official page | "Version 26.1.7.5654 · 1.03 GB · Windows 10, 11, or newer", Intel/AMD only, ARM unsupported | verified (page fetched) |
| Published checksum | none visible on the download page | verified absent |
| Authenticode validation | not performed locally | blocked (needs `authenticode-cli`/`signver` approval or a published digest) |

Resolved open question from the previous session: the `pe_arch: x86` report is **not** a
blocker. `flmint` now detects the NSIS marker and reports it as the expected 32-bit installer
stub (`installer_engine: nsis`). The 64-bit decision is made by the payload FL Studio extracts,
not by the stub. Status of "FL Studio 26 installs as 64-bit on this host": **not tested**.

Trial caveat that affects the Phase 2 gate: the official trial **cannot reopen saved `.flp`
projects**. Save/reopen testing therefore requires a legitimately unlocked license (verified from
the official page).

## 2. Wine and the WinTrust / certificate issue

| Item | Value | Status |
| --- | --- | --- |
| Wine installed | absent | verified |
| `~/.wine` prefix | absent | verified |
| Upstream stable Wine version | not obtained (`winehq.org` returned 403; GitLab is Anubis bot-challenged) | blocked |
| Wine MR 11824 state | could not be read (bot challenge) | blocked |
| Community claim | FL Studio 26.1.4+ breaks under Wine WinTrust (`WINTRUST_DefaultVerify` → `80096004`); workaround: 26.1.3 or lower, or the KitsuneDev Proton fork | unverified (community) |

Consequence for planning: the supplied installer is **26.1.7.5654**, i.e. inside the range the
community reports as broken. Two candidate mitigations, both unapproved so far:

1. Pin a runner that already carries the fix (DAW-GE-Proton candidate below) and reproduce the
   failure in an isolated prefix before trusting it.
2. Obtain an older official installer only if Image-Line offers it legitimately.

Selecting mitigation 2 must not involve third-party installer mirrors. Status: **blocked on
human decision**.

## 3. DAW-GE-Proton (candidate runner)

| Item | Value | Status |
| --- | --- | --- |
| Latest tag | `DAW-GE-Proton11-6c` (published 2026-09-13) | verified (GitHub API) |
| `DAW-GE-Proton11-6c.tar.gz` | 553,597,099 bytes, SHA-256 `aecf59518c1137028f6c47afc8e497064d6c5d0f206df6ea6d385dd0766f02d5` | verified (upstream-published digest) |
| `DAW-GE-Proton11-6c.sha512sum` | 156 bytes, SHA-256 `6e1cbdb39a896c1f257380f83145bf96299ecc3dbc2d55153788d3199a52a4d1` | verified |
| Community install recipe | extract `files/*` into `~/.var/app/com.usebottles.bottles/data/bottles/runners/<name>` | unverified (community), and it writes inside the Flatpak Bottles data dir |
| Downloaded / extracted / executed | no | verified |

Planning rule: if approved, the extracted runner goes into a **project-managed** directory
(`~/.local/share/flmint/profiles/<profile>/runners/`), with the upstream digest recorded in the
profile before extraction, rather than into a pre-existing Bottles directory.

## 4. Bottles (Flathub)

| Item | Value | Status |
| --- | --- | --- |
| Latest stable | 67.5 | verified (Flathub API) |
| License | GPL-3.0-only | verified |
| Runtime | `org.gnome.Platform/x86_64/50` | verified |
| Installed here | no (`~/.var/app` empty) | verified |
| Verified publisher flag | `flathub::verification::verified` (website method) | verified |

## 5. PipeASIO (experimental audio bridge)

| Item | Value | Status |
| --- | --- | --- |
| Latest release | v1.10.0 (2026-09-29) | verified (GitHub API) |
| Minimum PipeWire | 1.4.2 | verified (release metadata) |
| Minimum glibc | 2.38 | verified (release metadata) |
| Wine SDK used for build | `wine-11.18` | verified (release metadata) |
| `tested_runtimes` | empty list | verified — upstream publishes no tested-runner list |
| Driver DLL `.so` deps | `libc.so.6`, `libm.so.6`, `libpipewire-0.3.so.0` | verified |
| Flatpak Bottles support | **unsupported** ("Flatpak Steam is not supported, for the same reason as Flatpak Bottles (#36)") | verified (release notes text) |
| AppImage manager | 42,279,200 bytes, SHA-256 `cc48635112f1a4648afad936a489ae23e22cfe096da8261e15c629491fad29da` | verified digest |
| Arch x86_64 tarball | 1,003,895 bytes, SHA-256 `54f959381e1a60f05d0e3b662ed09b08d444d3161a248cd9964c23f47b057a5b` | verified digest |
| Per-file driver digests | recorded in `reports/upstream-candidates.json` | verified |
| Host gate | PipeWire 1.6.8 ≥ 1.4.2 and glibc 2.44 ≥ 2.38 | verified (version comparison only) |

Architectural consequence (this is the significant new finding): **Flatpak Bottles and PipeASIO do
not mix** per upstream's own release notes. That splits the experimental track into two options,
neither yet approved:

- **Option E1:** native (non-Flatpak) Wine installed into `~/.local/opt/flmint/wine/<version>`
  plus PipeASIO driver + manager — more moving parts, but the supported PipeASIO path.
- **Option E2:** Flatpak Bottles plus WineASIO/JACK — but JACK (`jackd`) is currently **absent**
  on this host and the user has no `@audio`/realtime group membership (`ulimit -r` = 0), so this
  path needs approved package installs and a session-policy change.

Status of both options: **not tested**, approval required.

## 6. WineASIO

Carried forward from the previous session as `v1.3.0` with digest
`f8bf74c871233f65e5befecc7b4f2629f2566f84e951e363af0ad51eae516a4c`: **candidate, not re-verified
this session**, and it depends on JACK which is absent here.

## 7. WebView2 / FL Cloud scope

| Item | Value | Status |
| --- | --- | --- |
| Official unlock path | Help → Unlock FL Studio → sign in (opens a browser), plus an offline unlock knowledge-base article | verified (official page) |
| Community claim | WebView2 leaves hanging processes; FL Cloud plugins may leak memory | unverified (community) |
| Decision | core DAW functionality is validated **without** FL Cloud; WebView2/login is a separately documented risk, never bypassed | agreed planning rule |

## 8. Ubuntu Studio / distro tooling

Ubuntu Studio packages are **not installed** on this host (verified by package query), and no
Ubuntu Studio installer behavior was inspected. Any package recipe that writes Ubuntu Studio
packages into an automatic installer is therefore **not allowed** until reviewed. See
`docs/os-migration-decision.md`.

## 9. Research tasks from HANDOFF section 4

| Task | Outcome |
| --- | --- |
| Is the WinTrust fix already in a stable Wine? | **blocked** (both Wine sites unreachable for this agent); treated as unfixed until proven otherwise |
| Can DAW-GE-Proton be used as a Bottles runner here? | metadata verified and pinned-able; runtime usability **not tested**; community path writes outside managed state, so `flmint` would use its own runner dir |
| PipeASIO registration requirements for this runner | prerequisites pass on paper (PipeWire/glibc); Flatpak Bottles unsupported per upstream; per-prefix registration still **not tested** |
| Are WebView2/FL Cloud required for acceptance? | no: core install/activation/save/export can be tested without FL Cloud; login path remains a known risk |
| Ubuntu Studio installer behavior | **not inspected**; no automatic package installs |
