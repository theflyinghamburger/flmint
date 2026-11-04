"""Official installer validation: presence, PE structure, SHA-256. Never executes the installer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import InstallerError

CHUNK = 1024 * 1024
PE_HEADER_WINDOW = 8192
ENGINE_SCAN_WINDOW = 2 * 1024 * 1024
MACHINE_X86 = 0x014C
MACHINE_X64 = 0x8664
_NSIS_MARKERS = (b"Nullsoft", b"NSIS")

ENGINE_NSIS = "nsis"
ENGINE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class InstallerInfo:
    path: Path
    display_path: str
    size_bytes: int
    sha256: str
    pe_arch: str  # x86-64 | x86 | unknown
    installer_engine: str  # nsis | unknown
    warnings: tuple[str, ...]

    def summary_lines(self) -> list[str]:
        return [
            f"installer: {self.display_path}",
            f"  size_bytes: {self.size_bytes}",
            f"  sha256: {self.sha256}",
            f"  pe_arch: {self.pe_arch}",
            f"  installer_engine: {self.installer_engine}",
        ] + [f"  warning: {w}" for w in self.warnings]


def display_path_for(path: Path, home: Path | None = None) -> str:
    home = home or Path.home()
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _read_pe_arch(path: Path, size: int) -> str:
    with open(path, "rb") as handle:
        head = handle.read(PE_HEADER_WINDOW)
    if len(head) < 0x40 or head[:2] != b"MZ":
        raise InstallerError(
            f"not a valid Windows PE file (missing MZ header): {path.name}",
            next_actions=("confirm this is the official Image-Line Windows .exe installer",),
        )
    lfanew = int.from_bytes(head[0x3C:0x40], "little")
    if lfanew <= 0 or lfanew + 6 > size:
        raise InstallerError(
            f"PE header offset out of range: {path.name}",
            next_actions=("re-download the installer from image-line.com",),
        )
    with open(path, "rb") as handle:
        handle.seek(lfanew)
        signature = handle.read(6)
    if signature[:4] != b"PE\x00\x00":
        raise InstallerError(
            f"not a valid Windows PE file (missing PE signature): {path.name}",
            next_actions=("confirm the file was fully downloaded and not truncated",),
        )
    machine = int.from_bytes(signature[4:6], "little")
    if machine == MACHINE_X64:
        return "x86-64"
    if machine == MACHINE_X86:
        return "x86"
    return "unknown"


def _detect_engine(path: Path, size: int) -> str:
    head_window = min(size, ENGINE_SCAN_WINDOW)
    with open(path, "rb") as handle:
        head = handle.read(head_window)
        tail = b""
        if size > head_window:
            handle.seek(max(0, size - 65536))
            tail = handle.read()
    if any(marker in head or marker in tail for marker in _NSIS_MARKERS):
        return ENGINE_NSIS
    return ENGINE_UNKNOWN


def validate_installer(path: Path, home: Path | None = None) -> InstallerInfo:
    """Validate without executing. Raises InstallerError with next actions."""
    if not path.exists():
        raise InstallerError(
            f"installer not found: {display_path_for(path, home)}",
            next_actions=(
                "download the official FL Studio Windows installer from image-line.com",
                "re-run with --installer /correct/path/flstudio_win64.exe",
            ),
        )
    if not path.is_file():
        raise InstallerError(
            f"installer path is not a regular file: {display_path_for(path, home)}",
            next_actions=("point --installer at the .exe file itself, not a directory",),
        )
    if path.suffix.lower() != ".exe":
        raise InstallerError(
            f"installer must be a Windows .exe: {path.name}",
            next_actions=("supply the official FL Studio Windows installer",),
        )
    size = path.stat().st_size
    if size == 0:
        raise InstallerError(
            f"installer is empty: {path.name}",
            next_actions=("re-download the installer",),
        )

    warnings: list[str] = []
    if size < 1024 * 1024:
        warnings.append("installer smaller than 1 MiB: likely truncated or not the full FL Studio installer")

    pe_arch = _read_pe_arch(path, size)
    engine = _detect_engine(path, size)
    if pe_arch == "x86" and engine == ENGINE_NSIS:
        warnings.append(
            "32-bit PE with NSIS markers: this is the expected NSIS installer stub; "
            "the installed FL Studio payload architecture is decided by the extracted files, not the stub"
        )
    elif pe_arch == "x86":
        warnings.append("32-bit PE: FL Studio 26 requires a 64-bit Windows installer")
    elif pe_arch == "unknown":
        warnings.append(f"unrecognized PE machine type: {pe_arch}")
    warnings.append(
        "Authenticode signature not validated locally; "
        "cross-check SHA-256 against the Image-Line download page"
    )

    return InstallerInfo(
        path=path,
        display_path=display_path_for(path, home),
        size_bytes=size,
        sha256=sha256_of(path),
        pe_arch=pe_arch,
        installer_engine=engine,
        warnings=tuple(warnings),
    )
