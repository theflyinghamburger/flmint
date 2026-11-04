from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass
class ProbeCall:
    name: str
    argv: tuple[str, ...]
    status: str
    exit_code: int | None
    stdout: str
    stderr: str


@dataclass
class FakeProber:
    calls: list[ProbeCall] = field(default_factory=list)
    outputs: dict[str, tuple[int, str]] = field(default_factory=dict)
    absent: set[str] = field(default_factory=set)
    timeouts: set[str] = field(default_factory=set)
    nonzero: set[str] = field(default_factory=set)

    def run(self, name: str, argv: list[str], *, timeout: float = 5.0):
        from flmint.probe import ProbeResult

        self.calls.append(
            ProbeCall(
                name=name,
                argv=tuple(argv),
                status="absent" if name in self.absent else "timeout" if name in self.timeouts else "ok",
                exit_code=None,
                stdout="",
                stderr="",
            )
        )
        if name in self.absent:
            return ProbeResult(name, tuple(argv), "absent", None, "", f"command not found: {name}")
        if name in self.timeouts:
            return ProbeResult(name, tuple(argv), "timeout", None, "", f"timeout after {timeout}s")
        exit_code, stdout = self.outputs.get(name, (0, ""))
        if exit_code != 0:
            return ProbeResult(name, tuple(argv), "nonzero", exit_code, stdout, stdout)
        return ProbeResult(name, tuple(argv), "ok", 0, stdout, "")

    def statuses(self) -> dict[str, str]:
        return {call.name: call.status for call in self.calls}


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def healthy_outputs() -> dict[str, tuple[int, str]]:
    return {
        "uname-release": (0, "7.3.0-10-generic\n"),
        "uname-machine": (0, "x86_64\n"),
        "lscpu": (0, fixture_text("lscpu.txt")),
        "free": (0, fixture_text("free-b.txt")),
        "df-disk": (0, fixture_text("df-blocks.txt")),
        "df-inodes": (0, fixture_text("df-inodes.txt")),
        "nvidia-smi": (0, fixture_text("nvidia-csv.txt")),
        "nvcc": (0, fixture_text("nvcc.txt")),
        "pipewire": (0, fixture_text("pipewire-168.txt")),
        "pipewire-pulse": (0, fixture_text("pipewire-168.txt")),
        "wpctl": (0, fixture_text("wpctl-status.txt")),
        "wine": (0, fixture_text("wine-9.txt")),
        "flatpak": (0, fixture_text("flatpak-version.txt")),
        "flatpak-list": (0, fixture_text("flatpak-list.txt")),
        "docker": (0, fixture_text("docker.txt")),
    }


def make_prober(**overrides) -> FakeProber:
    """Build a prober with sane 'healthy host' stub outputs, then apply overrides.

    Override semantics:
      - absent="name1,name2": commands report not found
      - timeout="name": commands report timeout
      - nonzero="name": commands report nonzero exit (with output captured)
      - outputs={"name": (exit_code, stdout)}: explicit replacement
    """
    outputs = healthy_outputs()
    absent = set((overrides.pop("absent", "") or "").split(",")) - {""}
    timeout = set((overrides.pop("timeout", "") or "").split(",")) - {""}
    nonzero = set((overrides.pop("nonzero", "") or "").split(",")) - {""}
    explicit_outputs = overrides.pop("outputs", {})
    outputs.update(explicit_outputs)
    prober = FakeProber(outputs=outputs, absent=absent, timeouts=timeout, nonzero=nonzero)
    for name in nonzero:
        prober.outputs[name] = (1, f"stub nonzero failure for {name}\n")
    return prober


def write_fake_pe(path: pathlib.Path, *, machine: int = 0x8664) -> pathlib.Path:
    """Write a tiny PE-like .exe (MZ header + PE signature + optional header magic)."""
    data = bytearray(b"MZ" + b"\x00" * 0x3A + (0x40).to_bytes(4, "little"))
    data += b"PE\x00\x00" + machine.to_bytes(2, "little") + b"\x00" * 0x80
    path.write_bytes(bytes(data))
    return path


def write_fake_nsis_pe(path: pathlib.Path, *, machine: int = 0x014C) -> pathlib.Path:
    """Write a 32-bit PE stub that also carries NSIS markers (like the FL Studio installer)."""
    data = bytearray(b"MZ" + b"\x00" * 0x3A + (0x40).to_bytes(4, "little"))
    data += b"PE\x00\x00" + machine.to_bytes(2, "little") + b"\x00" * 0x80
    data += b"NullsoftInst" + b"\x00" * 16 + b"NSIS"
    path.write_bytes(bytes(data))
    return path
