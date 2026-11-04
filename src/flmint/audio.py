"""Version parsing and compatibility gates for the audio stack."""

from __future__ import annotations

import re

PIPEWIRE_PIPEASIO_MIN: tuple[int, int, int] = (1, 4, 2)

_LIB_VERSION_RE = re.compile(r"libpipewire\s+(\d+\.\d+(?:\.\d+)?)")
_DOTTED_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")
_WINE_VERSION_RE = re.compile(r"wine-([0-9]+(?:\.[0-9]+)*)")
_NVCC_RELEASE_RE = re.compile(r"release\s+(\d+\.\d+)")
_FLATPAK_VERSION_RE = re.compile(r"Flatpak\s+(\d+\.\d+(?:\.\d+)?)")
_DOCKER_VERSION_RE = re.compile(r"Docker version\s+(\S+?)[,\s]")


def _version_tuple(version_text: str) -> tuple[int, int, int] | None:
    parts = version_text.split("-", 1)[0].split(".")
    if len(parts) < 2:
        return None
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return (major, minor, patch)


def parse_pipewire_version(text: str) -> tuple[int, int, int] | None:
    match = _LIB_VERSION_RE.search(text or "") or _DOTTED_VERSION_RE.search(text or "")
    if match is None:
        return None
    return _version_tuple(match.group(1))


def parse_wine_version(text: str) -> str | None:
    match = _WINE_VERSION_RE.search(text or "")
    return match.group(1) if match else None


def parse_nvcc_version(text: str) -> str | None:
    match = _NVCC_RELEASE_RE.search(text or "")
    return match.group(1) if match else None


def parse_flatpak_version(text: str) -> str | None:
    match = _FLATPAK_VERSION_RE.search(text or "")
    return match.group(1) if match else None


def parse_docker_version(text: str) -> str | None:
    match = _DOCKER_VERSION_RE.search(text or "")
    return match.group(1) if match else None


def parse_wpctl_audio_devices(text: str) -> list[dict[str, str]]:
    """Parse `wpctl status` Audio -> Devices block into {name, api} entries."""
    devices: list[dict[str, str]] = []
    in_audio = False
    in_devices = False
    for raw in (text or "").splitlines():
        line = raw.strip(" \t\u2502\u251c\u2514\u2500")
        if line == "Audio":
            in_audio, in_devices = True, False
            continue
        if line == "Video":
            in_audio, in_devices = False, False
            continue
        if not in_audio:
            continue
        if line.startswith("Devices"):
            in_devices = True
            continue
        if line.startswith(("Sinks", "Sources", "Filters", "Streams")):
            in_devices = False
            continue
        if in_devices and line:
            match = re.match(r"^\d+\.\s+(.+?)\s+\[([A-Za-z0-9_.-]+)\]", line)
            if match:
                devices.append({"name": match.group(1), "api": match.group(2)})
    return devices
