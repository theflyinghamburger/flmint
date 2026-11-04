"""flmint doctor: read-only host inventory with structured capabilities/blockers."""

from __future__ import annotations

import json
import os
import re
import socket
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audio import (
    PIPEWIRE_PIPEASIO_MIN,
    parse_docker_version,
    parse_flatpak_version,
    parse_nvcc_version,
    parse_pipewire_version,
    parse_wine_version,
    parse_wpctl_audio_devices,
)
from .downloads import opt_root
from .probe import Prober, ProbeResult

DISK_REQUIRED_BYTES = 12 * 1024**3  # phase 2 estimate floor: >= 12 GiB free
RAM_WARN_AVAILABLE_BYTES = 6 * 1024**3  # flag contention when < 6 GiB available

_DF_BLOCK_RE = re.compile(r"^\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+")
_DF_INODE_RE = re.compile(r"^\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+")


@dataclass
class HostFacts:
    schema_version: int = 1
    generated_at: str = ""
    hostname: str = ""
    os: dict[str, str] = field(default_factory=dict)
    kernel_release: str = ""
    machine_arch: str = ""
    session_type: str = "unknown"
    desktop: str = "unknown"
    cpu_model: str | None = None
    logical_cpus: int | None = None
    physical_cores: int | None = None
    memory_total_bytes: int | None = None
    memory_available_bytes: int | None = None
    swap_total_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_free_bytes: int | None = None
    disk_free_inodes: int | None = None
    disk_mount: str = ""
    nvidia: dict[str, Any] = field(default_factory=dict)
    cuda: dict[str, Any] = field(default_factory=dict)
    pipewire: dict[str, Any] = field(default_factory=dict)
    pipewire_pulse_present: bool = False
    wireplumber_present: bool = False
    audio_devices: list[dict[str, str]] = field(default_factory=list)
    wine: dict[str, Any] = field(default_factory=dict)
    wine_prefix_present: bool = False
    i386_loader_present: bool = False
    managed_runners: list[str] = field(default_factory=list)
    flatpak: dict[str, Any] = field(default_factory=dict)
    bottles_installed: bool = False
    docker: dict[str, Any] = field(default_factory=dict)
    installer: dict[str, Any] = field(default_factory=dict)
    probes: list[dict[str, Any]] = field(default_factory=list)
    capabilities: dict[str, bool | None] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


_COMPARE_KEYS = (
    "hostname",
    "session_type",
    "desktop",
    "os",
    "kernel_release",
    "machine_arch",
    "cpu_model",
    "logical_cpus",
    "physical_cores",
    "memory_total_bytes",
    "disk_total_bytes",
    "disk_mount",
    "nvidia",
    "cuda",
    "pipewire",
    "pipewire_pulse_present",
    "wireplumber_present",
    "audio_devices",
    "wine",
    "wine_prefix_present",
    "i386_loader_present",
    "managed_runners",
    "flatpak",
    "bottles_installed",
    "docker",
    "installer",
    "capabilities",
    "blockers",
)


def compare_facts(current: HostFacts, baseline_json: str) -> dict[str, Any]:
    baseline = json.loads(baseline_json)
    current_data = asdict(current)
    changes: list[dict[str, Any]] = []
    for key in _COMPARE_KEYS:
        old = baseline.get(key)
        new = current_data.get(key)
        if old != new:
            changes.append({"path": key, "baseline": old, "current": new})
    return {"schema_version": 1, "changed": bool(changes), "changes": changes}


def render_compare(comparison: dict[str, Any]) -> str:
    lines = ["doctor comparison", "-" * 60]
    if not comparison["changed"]:
        lines.append("no material host/capability drift since baseline")
        return "\n".join(lines)
    for change in comparison["changes"]:
        lines.append(f"changed {change['path']}:")
        lines.append(f"  baseline: {change['baseline']}")
        lines.append(f"  current:  {change['current']}")
    return "\n".join(lines)


def parse_os_release(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in (text or "").splitlines():
        match = re.match(r"^([A-Za-z_]+)=(.*)$", line.strip())
        if match:
            facts[match.group(1)] = match.group(2).strip('"')
    return facts


def _parse_lscpu(text: str) -> tuple[str | None, int | None, int | None]:
    fields: dict[str, str] = {}
    for line in (text or "").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields.setdefault(key.strip(), value.strip())
    model = fields.get("Model name") or None
    logical = _to_int(fields.get("CPU(s)"))
    cores_per_socket = _to_int(fields.get("Core(s) per socket"))
    sockets = _to_int(fields.get("Socket(s)"))
    physical = cores_per_socket * sockets if cores_per_socket and sockets else None
    return model, logical, physical


def _parse_free_bytes(text: str) -> tuple[int | None, int | None, int | None]:
    mem_total = mem_available = swap_total = None
    for line in (text or "").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "Mem:" and len(parts) >= 7:
            mem_total = _to_int(parts[1])
            mem_available = _to_int(parts[6])
        elif parts[0] == "Swap:" and len(parts) >= 2:
            swap_total = _to_int(parts[1])
    return mem_total, mem_available, swap_total


def _parse_df_blocks(text: str) -> tuple[int | None, int | None, str]:
    for line in (text or "").splitlines()[1:]:
        match = _DF_BLOCK_RE.match(line)
        if match:
            mount = line.split(None, 5)[-1].strip() if len(line.split(None, 5)) > 5 else ""
            return _to_int(match.group(1)), _to_int(match.group(3)), mount
    return None, None, ""


def _parse_df_inodes(text: str) -> int | None:
    for line in (text or "").splitlines()[1:]:
        match = _DF_INODE_RE.match(line)
        if match:
            return _to_int(match.group(3))
    return None


def _parse_nvidia_csv(text: str) -> dict[str, Any]:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    if not line:
        return {"present": False}
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return {"present": True, "raw": line}
    mib = _to_int(parts[2].split()[0]) if parts[2] else None
    return {"present": True, "name": parts[0], "driver_version": parts[1], "memory_total_mib": mib}


def _to_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _display_path(path: Path, home: Path) -> str:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def _managed_runners(home: Path) -> list[str]:
    root = opt_root(home)
    if not root.is_dir():
        return []
    found: set[str] = set()
    for component_dir in (d for d in root.iterdir() if d.is_dir()):
        level_one = [d for d in sorted(component_dir.iterdir()) if d.is_dir()]
        candidates = level_one + [sub for d in level_one for sub in sorted(d.iterdir()) if sub.is_dir()]
        for version_dir in candidates:
            if (version_dir / "files" / "bin" / "wine").is_file():
                found.add(f"{component_dir.name}/{version_dir.relative_to(component_dir)}")
    return sorted(found)


def installer_candidates(home: Path) -> list[Path]:
    """Only these well-known public directories are inspected (non-recursive)."""
    dirs = [home / "Downloads"]
    desktop = home / "Desktop"
    if desktop.is_dir():
        dirs.append(desktop)
    return dirs


def find_installer_candidates(home: Path, dirs: list[Path] | None = None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for directory in dirs if dirs is not None else installer_candidates(home):
        if not directory.is_dir():
            continue
        try:
            names = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for entry in names:  # non-recursive, no private folder sweeping
            try:
                name = entry.name
            except (OSError, UnicodeError):
                continue
            if not name.lower().startswith("flstudio") or not name.lower().endswith(".exe"):
                continue
            if not entry.is_file():
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            display = _display_path(entry, home)
            found.append({"name": name, "display_path": display, "size_bytes": size})
    return found


def collect_facts(
    prober: Prober,
    *,
    home: Path,
    os_release_file: Path = Path("/etc/os-release"),
    env: dict[str, str] | None = None,
    i386_loader_file: Path = Path("/lib/ld-linux.so.2"),
) -> HostFacts:
    env = env if env is not None else dict(os.environ)
    facts = HostFacts(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        hostname=socket.gethostname(),
        session_type=env.get("XDG_SESSION_TYPE", "unknown"),
        desktop=env.get("XDG_CURRENT_DESKTOP", "unknown"),
    )

    def probe(name: str, argv: list[str]) -> ProbeResult:
        result = prober.run(name, argv)
        facts.probes.append(
            {
                "name": result.name,
                "argv": list(result.argv),
                "status": result.status,
                "exit_code": result.exit_code,
            }
        )
        return result

    try:
        facts.os = parse_os_release(os_release_file.read_text(encoding="utf-8"))
    except OSError:
        facts.warnings.append("could not read /etc/os-release")

    uname_r = probe("uname-release", ["uname", "-r"])
    uname_m = probe("uname-machine", ["uname", "-m"])
    facts.kernel_release = uname_r.stdout.strip() if uname_r.usable else ""
    facts.machine_arch = uname_m.stdout.strip() if uname_m.usable else ""

    lscpu = probe("lscpu", ["lscpu"])
    if lscpu.usable:
        facts.cpu_model, facts.logical_cpus, facts.physical_cores = _parse_lscpu(lscpu.stdout)

    free = probe("free", ["free", "-b"])
    if free.usable:
        facts.memory_total_bytes, facts.memory_available_bytes, facts.swap_total_bytes = _parse_free_bytes(
            free.stdout
        )

    df = probe("df-disk", ["df", "-P", "-B1", str(home)])
    if df.usable:
        facts.disk_total_bytes, facts.disk_free_bytes, facts.disk_mount = _parse_df_blocks(df.stdout)
    df_inodes = probe("df-inodes", ["df", "-P", "-i", str(home)])
    if df_inodes.usable:
        facts.disk_free_inodes = _parse_df_inodes(df_inodes.stdout)

    nvidia = probe(
        "nvidia-smi", ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]
    )
    facts.nvidia = _parse_nvidia_csv(nvidia.stdout) if nvidia.usable else {"present": False}

    nvcc = probe("nvcc", ["nvcc", "--version"])
    cuda_version = parse_nvcc_version(nvcc.stdout) if nvcc.usable else None
    facts.cuda = {"present": cuda_version is not None, "version": cuda_version}

    pipewire = probe("pipewire", ["pipewire", "--version"])
    pw_version = parse_pipewire_version(pipewire.stdout) if pipewire.usable else None
    facts.pipewire = {
        "present": pw_version is not None,
        "version": list(pw_version) if pw_version else None,
        "raw_version": f"{pw_version[0]}.{pw_version[1]}.{pw_version[2]}" if pw_version else None,
    }
    pw_pulse = probe("pipewire-pulse", ["pipewire-pulse", "--version"])
    facts.pipewire_pulse_present = (
        parse_pipewire_version(pw_pulse.stdout) is not None if pw_pulse.usable else False
    )

    wpctl = probe("wpctl", ["wpctl", "status"])
    if wpctl.usable:
        facts.audio_devices = parse_wpctl_audio_devices(wpctl.stdout)
        facts.wireplumber_present = "WirePlumber" in wpctl.stdout

    wine = probe("wine", ["wine", "--version"])
    wine_version = parse_wine_version(wine.stdout) if wine.usable else None
    facts.wine = {"present": wine_version is not None, "version": wine_version}
    facts.wine_prefix_present = (home / ".wine").is_dir()
    facts.i386_loader_present = i386_loader_file.is_file()
    facts.managed_runners = _managed_runners(home)
    if facts.managed_runners:
        facts.warnings.append(
            "extracted flmint-managed runner(s) present under ~/.local/opt/flmint: "
            + ", ".join(facts.managed_runners)
        )

    flatpak_version = probe("flatpak", ["flatpak", "--version"])
    flatpak_v = parse_flatpak_version(flatpak_version.stdout) if flatpak_version.usable else None
    facts.flatpak = {"present": flatpak_v is not None, "version": flatpak_v}
    if flatpak_v is not None:
        bottles = probe("flatpak-list", ["flatpak", "list"])
        facts.bottles_installed = bottles.usable and "com.usebottles.bottles" in bottles.stdout

    docker = probe("docker", ["docker", "--version"])
    docker_v = parse_docker_version(docker.stdout) if docker.usable else None
    facts.docker = {"present": docker_v is not None, "version": docker_v}

    searched_dirs = installer_candidates(home)
    installers = find_installer_candidates(home, searched_dirs)
    facts.installer = {
        "found": bool(installers),
        "count": len(installers),
        "candidates": installers,
        "searched_dirs": [_display_path(d, home) for d in searched_dirs],
        "hashed": False,
        "note": "presence only; flmint plan validates and hashes on request, never executes",
    }

    _evaluate(facts)
    return facts


def _evaluate(facts: HostFacts) -> None:
    pw = tuple(facts.pipewire.get("version") or ()) or None
    caps: dict[str, bool | None] = {
        "pipewire_present": facts.pipewire.get("present"),
        "pipewire_meets_pipeasio_min": None if pw is None else pw >= PIPEWIRE_PIPEASIO_MIN,
        "pipewire_pulse_present": facts.pipewire_pulse_present,
        "wireplumber_present": facts.wireplumber_present,
        "nvidia_gpu_present": facts.nvidia.get("present"),
        "cuda_toolkit_present": facts.cuda.get("present"),
        "wine_installed": facts.wine.get("present"),
        "i386_loader_present": facts.i386_loader_present,
        "flmint_runner_installed": bool(facts.managed_runners),
        "flatpak_installed": facts.flatpak.get("present"),
        "bottles_installed": facts.bottles_installed,
        "docker_installed": facts.docker.get("present"),
        "official_installer_found": facts.installer.get("found"),
        "disk_headroom_ok": (
            None if facts.disk_free_bytes is None else facts.disk_free_bytes >= DISK_REQUIRED_BYTES
        ),
        "ram_headroom_ok": (
            None
            if facts.memory_available_bytes is None
            else facts.memory_available_bytes >= RAM_WARN_AVAILABLE_BYTES
        ),
    }
    facts.capabilities = caps

    if caps["pipewire_meets_pipeasio_min"] is False:
        facts.blockers.append(
            "PipeWire older than 1.4.2: PipeASIO path blocked "
            "until a human approves an audited PipeWire update"
        )
    elif caps["pipewire_meets_pipeasio_min"] is None:
        facts.blockers.append("PipeWire not detected: experimental PipeASIO gate cannot be evaluated")
    if (
        caps["wine_installed"] is False
        and caps["bottles_installed"] is False
        and not facts.managed_runners
    ):
        facts.blockers.append(
            "no Wine/Bottles runtime present (Phase 2 prerequisite; human approval required)"
        )
    if caps["official_installer_found"] is False:
        facts.blockers.append(
            "official FL Studio installer not found in checked dirs; supply --installer PATH"
        )
    if caps["disk_headroom_ok"] is False:
        facts.blockers.append("less than 12 GiB free on $HOME mount")

    if caps["pipewire_meets_pipeasio_min"] is True:
        facts.warnings.append(
            f"PipeWire {facts.pipewire.get('raw_version')} satisfies the documented "
            "PipeASIO >=1.4.2 prerequisite (gate check only, not a runtime test)"
        )
    if caps["docker_installed"] is False:
        facts.warnings.append("docker absent (optional for the AI coexistence track)")
    if caps["ram_headroom_ok"] is False:
        facts.warnings.append("less than 6 GiB RAM currently available: defer heavy builds/benchmarks")
    os_id = facts.os.get("ID", "")
    version_id = facts.os.get("VERSION_ID", "")
    if os_id == "ubuntu" and version_id and not version_id.endswith(".04"):
        facts.warnings.append(
            f"Ubuntu {version_id} appears to be a non-LTS release: "
            "acceptable for experiments, verify support window"
        )


TextRenderer = Callable[[HostFacts], str]


def _installer_text(facts: HostFacts) -> str:
    candidates = facts.installer.get("candidates") or []
    if not candidates:
        return "absent in checked dirs"
    first = candidates[0]
    return f"{first['display_path']} ({first['size_bytes']} bytes)"


_TEXT_ORDER: tuple[tuple[str, TextRenderer], ...] = (
    (
        "os",
        lambda f: (
            f"{f.os.get('NAME', '?')} {f.os.get('VERSION_ID', '')} "
            f"({f.os.get('VERSION_CODENAME', '')})"
        ),
    ),
    ("kernel", lambda f: f.kernel_release or "(unknown)"),
    ("arch", lambda f: f.machine_arch or "(unknown)"),
    ("session", lambda f: f"{f.session_type} / {f.desktop}"),
    (
        "cpu",
        lambda f: (
            f"{f.cpu_model or '?'} ({f.logical_cpus or '?'} logical / "
            f"{f.physical_cores or '?'} cores)"
        ),
    ),
    (
        "memory",
        lambda f: (
            f"total {f.memory_total_bytes // 1024**2 if f.memory_total_bytes else '?'} MiB, "
            f"available {f.memory_available_bytes // 1024**2 if f.memory_available_bytes else '?'} MiB"
        ),
    ),
    (
        "disk",
        lambda f: (
            f"{f.disk_mount or '?'}: free {f.disk_free_bytes // 1024**3 if f.disk_free_bytes else '?'} GiB "
            f"(inodes free {f.disk_free_inodes or '?'})"
        ),
    ),
    (
        "gpu",
        lambda f: f"{f.nvidia.get('name', 'absent')} driver {f.nvidia.get('driver_version', '-')}",
    ),
    ("cuda", lambda f: f"{f.cuda.get('version') or 'absent'}"),
    (
        "pipewire",
        lambda f: (
            f"{f.pipewire.get('raw_version') or 'absent'} (pulse: {f.pipewire_pulse_present}, "
            f"wireplumber: {f.wireplumber_present})"
        ),
    ),
    ("audio devices", lambda f: ", ".join(d["name"] for d in f.audio_devices) or "none detected"),
    (
        "wine",
        lambda f: (
            f"{f.wine.get('version') or 'absent'} (prefix ~/.wine: {f.wine_prefix_present}; "
            f"i386 loader /lib/ld-linux.so.2: {f.i386_loader_present})"
        ),
    ),
    (
        "flatpak",
        lambda f: f"{f.flatpak.get('version') or 'absent'} (bottles: {f.bottles_installed})",
    ),
    ("docker", lambda f: f"{f.docker.get('version') or 'absent'}"),
    ("flmint runners", lambda f: ", ".join(f.managed_runners) or "none installed"),
    ("installer", _installer_text),
)


def render_text(facts: HostFacts) -> str:
    lines = [f"flmint doctor (read-only) — {facts.generated_at}", "=" * 60]
    for label, getter in _TEXT_ORDER:
        lines.append(f"{label + ':':<16} {getter(facts)}")
    lines.append("-" * 60)
    lines.append("capabilities:")
    for key in sorted(facts.capabilities):
        value = facts.capabilities[key]
        marker = "yes" if value is True else ("no" if value is False else "unknown")
        lines.append(f"  {key}: {marker}")
    if facts.blockers:
        lines.append("blockers:")
        lines.extend(f"  - {b}" for b in facts.blockers)
    if facts.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {w}" for w in facts.warnings)
    probe_statuses = ", ".join(f"{p['name']}={p['status']}" for p in facts.probes)
    lines.append(f"probes: {probe_statuses}")
    return "\n".join(lines)
