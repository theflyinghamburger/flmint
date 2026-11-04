"""Safe read-only command probes: argument arrays, timeouts, sanitization, absence handling."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

MAX_OUTPUT_CHARS = 4096

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_REDACTIONS = (
    (re.compile(r"cookie:\S+", re.IGNORECASE), "cookie:[redacted]"),
    (re.compile(r"(password|passwd|token|secret|api[-_]?key)\s*[:=]\s*\S+", re.IGNORECASE), r"\1=[redacted]"),
)

OK = "ok"
NONZERO = "nonzero"
ABSENT = "absent"
TIMEOUT = "timeout"
ERROR = "error"


@dataclass(frozen=True)
class ProbeResult:
    name: str
    argv: tuple[str, ...]
    status: str  # ok | nonzero | absent | timeout | error
    exit_code: int | None
    stdout: str
    stderr: str

    @property
    def usable(self) -> bool:
        return self.status in (OK, NONZERO) and self.exit_code == 0


def sanitize(text: str) -> str:
    cleaned = _CONTROL_CHARS.sub("", text or "")
    for pattern, replacement in _REDACTIONS:
        cleaned = pattern.sub(replacement, cleaned)
    if len(cleaned) > MAX_OUTPUT_CHARS:
        cleaned = cleaned[:MAX_OUTPUT_CHARS] + " ...[truncated]"
    return cleaned


class Prober(Protocol):
    def run(self, name: str, argv: list[str], *, timeout: float | None = None) -> ProbeResult: ...


class CommandProber:
    """Runs argv as an argument array (never shell=True). Read-only by convention."""

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def run(self, name: str, argv: list[str], *, timeout: float | None = None) -> ProbeResult:
        argv_tuple = tuple(argv)
        if not argv or any(not isinstance(a, str) or not a for a in argv):
            return ProbeResult(name, argv_tuple, ERROR, None, "", "invalid argv")
        if shutil.which(argv[0]) is None:
            return ProbeResult(name, argv_tuple, ABSENT, None, "", f"{argv[0]}: command not found")
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout if timeout is not None else self.timeout,
                check=False,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                name, argv_tuple, TIMEOUT, None, "", f"timed out after {timeout or self.timeout}s"
            )
        except OSError as exc:
            return ProbeResult(name, argv_tuple, ERROR, None, "", sanitize(str(exc)))
        status = OK if proc.returncode == 0 else NONZERO
        return ProbeResult(
            name, argv_tuple, status, proc.returncode, sanitize(proc.stdout), sanitize(proc.stderr)
        )
