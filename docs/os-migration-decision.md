# OS migration decision (based on the audited host)

Decision date: 2026-11-03. Method: read-only host inspection plus upstream metadata. No package,
driver, kernel, PipeWire, or OS change was made. Status labels: `verified`, `unverified`,
`hypothesis`, `not tested`, `blocked`.

## Short answer

**Do not migrate the OS as part of this project right now.** The premise that "Mint 22.3 blocks
PipeASIO" is **not applicable to this host** (the host is not Linux Mint), and no PipeASIO version
blocker is measurable here: PipeWire `1.6.8` and glibc `2.44` already exceed PipeASIO's published
minimums (`1.4.2` / `2.38`). **Xubuntu 26.04 LTS would not fix any specific measured blocker**,
because the measured blockers are all audio-stack-independent (Wine absent, WinTrust status
unknown, no pinned runner, no provenance checksum). The only real argument for 26.04 LTS is the
support window, which is a maintenance decision, not a compatibility fix.

Recommendation: keep Ubuntu 26.10 for the approved Phase 2 experiments, and treat a **fresh**
26.04 LTS install as a separate, human-approved maintenance milestone before the setup is called
production-stable, because 26.10 standard security maintenance ends **Jul 2027**.

## Verified host facts (audited this session)

| Fact | Value | Source |
| --- | --- | --- |
| Distribution | Ubuntu `26.10 (stonking)` | `/etc/os-release`, `reports/host-audit.json` |
| Is it Linux Mint? | no (`/etc/linuxmint/info` absent) | direct check |
| Kernel | `7.3.0-10-generic` | audit |
| Session | `x11` / XFCE | audit |
| CPU | AMD Ryzen 7 5700X, 16 logical / 8 physical | audit |
| Memory | 64219 MiB total, 9536 MiB available at audit time | audit |
| Disk `/` | 175 GiB free, 14689732 free inodes | audit |
| GPU / driver | NVIDIA RTX 3090, `580.178.04` (`nvidia-driver-580-open`) | audit + `dpkg -l` |
| CUDA toolkit | `12.4` | audit |
| PipeWire | `1.6.8-1ubuntu4` (`pipewire`, `pipewire-bin`, `pipewire-pulse` installed) | `dpkg -l` |
| glibc | `2.44` | `getconf GNU_LIBC_VERSION` |
| Audio hardware | Focusrite **Scarlett Solo USB** is the current default PipeWire sink; Brio 100 webcam present | `wpctl status` |
| PipeWire tooling | `pw-dump`, `pw-cli`, `wpctl` present; `pw-monjack` absent | direct check |
| JACK | `jackd` / `qjackctl` absent | direct check |
| Realtime limits | user `ulimit -r` = `0`; no `@audio` limits entries found | direct check |
| Flatpak | `1.18.4`; **no user Flatpak apps** (`~/.var/app` does not exist) | audit + direct check |
| Wine / prefix | absent, `~/.wine` absent | audit + direct check |
| Ubuntu Studio packages | not installed | `dpkg -l` |
| Docker | absent | audit |

## Verified release-cycle facts (Canonical release-cycle page)

| Release | Released | Standard security maintenance |
| --- | --- | --- |
| Ubuntu 26.10 (interim) | Oct 2026 | **Jul 2027** |
| Ubuntu 26.04 LTS | Apr 2026 | **May 2031** (ESM to May 2036, legacy add-on to May 2041) |
| Ubuntu 24.04 LTS | Apr 2024 | May 2029 |

Canonical states interim releases receive **9 months** of updates and recommends LTS for
long-term/production use. Canonical also warns that **flavor (e.g. Xubuntu) release cycles and
support policies may differ** from Ubuntu's — so "Xubuntu 26.04 inherits exactly the Ubuntu LTS
window" is treated as **unverified** until checked on the Xubuntu site.

## Question 1 — Is Linux Mint 22.3 blocking PipeASIO?

Answer: **not on this host; the question is moot here.** Verified: this workstation runs Ubuntu
26.10 and has no Mint marker files. The earlier project discussion assumed a Mint 22.3 install;
that assumption no longer matches reality.

Secondary answer for the record: PipeASIO v1.10.0 publishes `minimum_pipewire: 1.4.2` and
`minimum_glibc: 2.38`. This host passes both (`1.6.8`, `2.44`) — **gate check only, not a runtime
test**. What was **not** verified: Mint 22.3's PipeWire version, and therefore whether an older
Mint would in fact have failed that gate. Any claim that Mint 22.3 "blocks PipeASIO" remains
`unverified` and is not used for planning.

## Question 2 — Would Xubuntu 26.04 fix the specific blocker?

Answer: **no specific measured blocker exists for it to fix.** The blockers that actually stop
Phase 2 are distro-independent:

1. No Wine/Proton runtime installed, and none pinned (`verified`).
2. WinTrust fix status upstream is unreadable (Wine site 403 / GitLab bot challenge) → `blocked`.
3. Community claim that FL Studio `26.1.4+` breaks WinTrust is unverified; the local installer is
   `26.1.7.5654`, i.e. in the claimed affected range → `unverified` risk, not a host fact.
4. No official Image-Line SHA-256 published → provenance review `blocked`.
5. PipeASIO upstream release notes state Flatpak (Steam **and Bottles**) is unsupported → this is
   an architectural constraint that an OS change does not solve; only the Wine packaging choice
   (native vs Flatpak) does.
6. Bottles is not installed, and installing Flatpak apps is an approval-gated action.

What 26.04 LTS *would* buy is time (support until May 2031 vs Jul 2027) and possibly fewer
mid-experiment distro upgrades. What it would *not* buy is the WinTrust fix, a pinned runner, or a
published installer checksum.

Migration cost note (`hypothesis`, not tested): going from a newer interim release (26.10) to an
older LTS (26.04) is not an in-place upgrade path, so it would mean a fresh install plus backup and
restore of the FL Studio state — a much larger, riskier operation than the Phase 2 work itself. It
should never be combined with FL Studio experimentation in the same window.

## Question 3 — Is Ubuntu Studio (26.04 flavor) the better base?

Not established. Ubuntu Studio's audio tooling (JACK, Cadence, low-latency kernel variants) is
**not installed on this host**, and its installer behavior was never inspected. Two observations
matter:

- PipeWire is *already* the working audio stack here (`pipewire` 1.6.8 + PulseAudio compatibility +
  WirePlumber), which is the stack PipeASIO targets. Installing Ubuntu Studio's JACK tooling would
  serve the **WineASIO fallback** track, not the PipeASIO track.
- Ubuntu Studio package recipes must not be wired into any automatic `flmint` installer without
  review; that is explicitly out of scope for Phase 0/1.

## Decision record

| Decision | Status |
| --- | --- |
| Keep Ubuntu 26.10 as the experimentation host for Phase 2/3 (approval-gated) | **proposed, awaiting human approval** |
| No OS migration, no distro flavor install, no kernel/PipeWire/driver change | **binding rule for Phase 0/1 (followed)** |
| Schedule a separate decision for a fresh 26.04 LTS install before treating the setup as long-lived | **proposed milestone, not started** |
| Re-audit the host after any distro change and re-pin components afterwards | **planned** |
| Keep a documented Windows fallback for critical projects (FL Studio trial cannot reopen saved `.flp` files) | **binding planning rule** |

## What would change this decision

- Reproduced WinTrust failure with the pinned runner → then the decision becomes "which runner
  version fixes it", still not an OS decision.
- PipeASIO failing on PipeWire 1.6.8 in real measurements → then the audio stack, not the distro,
  is investigated first (`pw-dump`/`wpctl` capture + PipeASIO logs).
- A decision to require JACK/WineASIO instead of PipeASIO → then package installs (`jackd`,
  `qjackctl`) and realtime scheduling (`@audio` group / `ulimit -r`) become approval-gated host
  changes that need explicit human sign-off.
