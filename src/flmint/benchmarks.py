"""Benchmark harness stubs. No measurement has been performed; nothing is fabricated."""

from __future__ import annotations

from .errors import NotYetImplementedError


def bench_audio(profile: str, sample_rate: int, buffers: str) -> None:
    raise NotYetImplementedError(
        f"bench audio (profile={profile}, sr={sample_rate}, buffers={buffers}) is not implemented (Phase 3)",
        next_actions=(
            "audio benchmarking requires the installed prefix + "
            "a documented human-created FL Studio test project",
            "XRUN/underrun evidence must come from PipeWire logs; "
            "round-trip latency needs loopback measurement",
        ),
    )


def bench_ai(model: str | None, backend: str) -> None:
    if model is None:
        raise NotYetImplementedError(
            f"bench ai backend '{backend}' skipped: no model supplied and flmint never downloads models",
            next_actions=("supply --model /path/to/model.gguf (user-provided path only)",),
        )
    raise NotYetImplementedError(
        f"bench ai model '{model}' backend '{backend}' is not implemented (Phase 5)",
        next_actions=("schedule as a bounded workload; never during active recording sessions",),
    )
