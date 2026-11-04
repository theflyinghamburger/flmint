# Benchmark plan and measurement rules

`flmint bench audio` and `flmint bench ai` are **stubs** (`NotYetImplementedError`, exit 2). This
file records *how* they will be measured, which tools actually exist on this host, and what must not
be claimed before measurements exist.

## Verified measurement tooling on this host

| Tool | Status | Use |
| --- | --- | --- |
| `nvidia-smi` | present (reports RTX 3090, `580.178.04`, 24576 MiB) | GPU utilization/VRAM/power sampling |
| `mpstat` | present | per-CPU utilization during playback/inference |
| `perf` | present | optional profiling, not used by default |
| `lspci` | present | device confirmation |
| `glxinfo` | present | GL renderer confirmation (X11 session) |
| `pw-dump`, `pw-cli`, `wpctl` | present | PipeWire device/stream/graph inspection |
| `pw-monjack` | **absent** | not usable for XRUN monitoring yet |
| `jackd`, `qjackctl` | **absent** | WineASIO path unusable until approved installs |
| `nvtop` | absent | optional, would need approval to install |
| `ulimit -r` | `0` | no realtime scheduling priority for this user today |

## Audio benchmark (Phase 3) — planned harness

Baseline first, experiments second, one variable at a time:

1. **Baseline row:** FL Studio's built-in ASIO/Wine audio path on the pinned runner, Scarlett Solo
   output, 48 kHz, buffer sizes 1024 → 512 → 256 (optionally 128), one fixed human-authored test
   project, no cloud plugins.
2. **Evidence captured per row:** FL Studio buffer setting, PipeWire device/stream state
   (`pw-dump`, `wpctl status`), audible glitch report, XRUN evidence if obtainable, `mpstat` CPU,
   process tree before/after (orphaned-process check), prefix snapshot name.
3. **Pass criteria (from HANDOFF section 9):** 20 consecutive launch/exit runs without failures or
   orphaned critical processes; 30 minutes clean playback at the chosen stable buffer size, then a
   4-hour soak; save/reopen of the test project; playable offline WAV export.
4. **Round-trip latency** is only reported when a loopback measurement exists. Candidate methods,
   all currently `not tested`:
   - PipeWire loopback routing (`pw-cli`/`wpctl` graph manipulation) — availability on this host
     `not verified`.
   - Hardware loopback on the Scarlett Solo — capability `not verified`.
   - Two-channel measurement with an external cable — requires human setup.
5. **Prohibited claims:** `buffer_frames / sample_rate` may never be reported as latency; FL
   Studio's internal latency counter is app-reported only; no ASIO driver name may be listed as
   "working" without a captured session log.

## Realtime/priority policy

No permanent CPU governor change, no blanket realtime priority, no `@audio` group membership, no
`/etc/security/limits.d` edit. `ulimit -r` is 0 today and stays 0 unless a human approves a scoped,
reversible change per test session. Any experiment that needs it is documented with the exact command
and reverted on regression.

## GPU / AI coexistence benchmark (Phase 5) — planned harness

Blocked on a human-supplied model; no model has been provided yet.

1. `llama.cpp` inference with a **user-provided** model file + pinned build + recorded model SHA-256.
   `flmint` will not download models.
2. Recorded per run: driver (`580.178.04`), CUDA toolkit (`12.4` presence verified), model digest,
   quantization, context length, batch size, tokens/sec, time-to-first-token, VRAM (via `nvidia-smi`),
   peak RSS, power/thermal samples, and the `music` vs `ai` background-load profile.
3. Coexistence rows: FL Studio idle, FL Studio playback + CPU stress, FL Studio playback + GPU
   inference. **Never run full-intensity GPU tests during an active recording session.**
4. Reporting rule: medians plus spread across repeated runs, never a single best run; comparisons
   only against the same model, same runner, same audio buffer, same interface.

## What is currently measured (the honest list)

Measured now: PipeWire 1.6.8 presence, glibc 2.44, driver 580.178.04, GPU 24576 MiB, disk headroom,
CPU topology, tool availability/absence listed above.

Not measured at all yet: FL Studio startup time, playback stability, XRUNs, underruns, plugin load
times, round-trip latency, token throughput, VRAM under inference, thermal behavior. Any benchmark
number appearing in a future report must cite the command, the pinned versions, the prefix snapshot
name, and the captured log file.
