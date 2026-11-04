"""Launch FL Studio in a profile prefix with the pinned runner, and stop it.

The environment is built from scratch (never inherited wholesale) and mirrors the launch accepted in
``reports/pipeasio-experimental.md`` and re-verified on 2026-11-04/05: explicit ``WINEPREFIX`` (never
``~/.wine``), ``WINEDLLPATH`` only when the profile carries PipeASIO, ``XDG_RUNTIME_DIR`` for PipeWire, and
Mono/Gecko disabled. Preflight refuses known host hazards before anything runs.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .downloads import opt_root
from .errors import FlmintError, FlmintUsageError
from .manifest import Profile
from .projects import PROJECT_SUFFIX, fl_install_dir
from .snapshots import prefix_path

RUNNER_COMPONENT = "daw-ge-proton"
PIPEASIO_COMPONENT = "pipeasio"
SAFE_PATH = "/usr/bin:/bin"
DLL_OVERRIDES = "mscoree,mshtml="
DEFAULT_WINE_DEBUG = "-all"
VKD3D_DLLS = ("libvkd3d-1.dll", "libvkd3d-shader-1.dll", "libvkd3d-utils-1.dll")
X11_DRIVER_SECTION = "[Software\\\\Wine\\\\X11 Driver]"
# Setting either to "N" made winex11 fall back to its no-resolution path, which crashed Xorg on this
# host (NVIDIA driver, scaled + rotated monitors) on 2026-11-04.
X11_HAZARDS = ('"UseXRandR"="N"', '"UseXVidMode"="N"')
_WINE_DEBUG_RE = re.compile(r"^[A-Za-z0-9_,+\-]+$")

Popen = Callable[..., Any]


@dataclass(frozen=True)
class LaunchSpec:
    profile: str
    argv: tuple[str, ...]
    env: dict[str, str]
    prefix: Path
    runner: Path
    project: Path | None
    log_path: Path
    pid_path: Path
    warnings: tuple[str, ...]


def state_dir(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    environ = os.environ if env is None else env
    base = environ.get("XDG_STATE_HOME")
    root = Path(base) if base else (home or Path.home()) / ".local" / "state"
    return root / "flmint"


def runner_root(profile: Profile, home: Path | None = None) -> Path:
    """Resolve the pinned runner root (the directory holding ``files/bin/wine``)."""
    component = next((item for item in profile.components if item.id == RUNNER_COMPONENT), None)
    if component is None or not component.version or not component.sha256:
        raise FlmintError(
            f"profile '{profile.name}' has no pinned '{RUNNER_COMPONENT}' runner (version + sha256)",
            next_actions=("pin the runner in the profile YAML first (explicit human approval)",),
        )
    base = opt_root(home) / component.id / component.version
    # Release tarballs carry a top-level directory of the same name, so the root is usually nested.
    for root in (base / component.version, base):
        if (root / "files" / "bin" / "wine").is_file():
            return root
    raise FlmintError(
        f"pinned runner {component.version} is not extracted under {base}",
        next_actions=(
            f"flmint fetch --profile {profile.name} --component {component.id} --approve --extract",
        ),
    )


def windows_path(path: Path) -> str:
    """Map an absolute Linux path onto Wine's ``Z:`` drive."""
    return "Z:" + str(path).replace("/", "\\")


def x11_hazards(prefix: Path) -> list[str]:
    """Return hazardous winex11 values set in the prefix's ``user.reg``."""
    try:
        text = (prefix / "user.reg").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("["):
            in_section = line.split("]", 1)[0] + "]" == X11_DRIVER_SECTION
        elif in_section and line.strip() in X11_HAZARDS:
            found.append(line.strip())
    return found


def prerequisite_warnings(prefix: Path) -> list[str]:
    """Non-fatal gaps that Proton would normally fill but a direct ``wine`` launch does not."""
    warnings: list[str] = []
    windows = prefix / "drive_c" / "windows"
    for arch_dir in ("system32", "syswow64"):
        missing = [dll for dll in VKD3D_DLLS if not (windows / arch_dir / dll).exists()]
        if missing:
            warnings.append(
                f"{arch_dir} lacks {', '.join(missing)}: wined3d/d3d9/dxgi will fail (FLEX and other "
                "Direct3D plugins crash); copy them from the runner's files/lib/vkd3d"
            )
    if not (windows / "Fonts" / "Verdana.ttf").exists():
        warnings.append("Fonts/Verdana.ttf missing: FLEX's engine crashes opening it")
    return warnings


def running_pids(prefix: Path, runner: Path, proc: Path = Path("/proc")) -> list[int]:
    """PIDs of this user's Wine processes (executable inside the runner) bound to this prefix.

    Linux programs that Wine spawned (a browser opened from a help link, dbus-launch) inherit WINEPREFIX
    but are not Wine processes and survive ``wineserver -k``, so the executable must be the runner's.
    """
    needle = f"WINEPREFIX={prefix}".encode()
    runner_prefix = f"{runner}/"
    pids: list[int] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            environ = (entry / "environ").read_bytes()
            exe = os.readlink(entry / "exe")
        except OSError:
            continue
        if needle in environ.split(b"\x00") and exe.startswith(runner_prefix):
            pids.append(int(entry.name))
    return sorted(pids)


def _checked_prefix(profile: Profile) -> Path:
    prefix = prefix_path(profile.name)
    if not prefix.is_dir():
        raise FlmintError(
            f"no prefix for profile '{profile.name}': {prefix}",
            next_actions=(f"review: flmint plan --profile {profile.name}",),
        )
    hazards = x11_hazards(prefix)
    if hazards:
        raise FlmintError(
            f"prefix sets {', '.join(hazards)} under X11 Driver: this crashed Xorg on this host",
            next_actions=(
                "remove those values from user.reg (wineserver stopped, snapshot first) before launching",
            ),
        )
    return prefix


def _checked_project(project: Path | None) -> Path | None:
    if project is None:
        return None
    resolved = project.expanduser().resolve()
    if resolved.suffix.lower() != PROJECT_SUFFIX or not resolved.is_file():
        raise FlmintUsageError(
            f"project must be an existing {PROJECT_SUFFIX} file: {project}",
            next_actions=("create one: flmint new-project NAME",),
        )
    return resolved


def build_spec(
    profile: Profile,
    *,
    project: Path | None = None,
    wine_debug: str = DEFAULT_WINE_DEBUG,
    pipeasio_debug: bool = False,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    now: datetime | None = None,
) -> LaunchSpec:
    """Validate everything and assemble argv + a clean environment. Executes nothing."""
    environ = os.environ if env is None else env
    home = home or Path.home()
    prefix = _checked_prefix(profile)
    runner = runner_root(profile, home)
    fl64 = fl_install_dir(prefix) / "FL64.exe"
    if not _WINE_DEBUG_RE.match(wine_debug):
        raise FlmintUsageError(
            f"invalid --wine-debug '{wine_debug}'",
            next_actions=("use Wine channel syntax such as -all or err+all,warn+seh",),
        )
    display = environ.get("DISPLAY")
    if not display:
        raise FlmintError("DISPLAY is not set; FL Studio needs the X session", next_actions=())

    resolved_project = _checked_project(project)

    clean: dict[str, str] = {
        "HOME": str(home),
        "PATH": SAFE_PATH,
        "LANG": environ.get("LANG") or "C.UTF-8",
        "DISPLAY": display,
        "WINEPREFIX": str(prefix),
        "WINEDEBUG": wine_debug,
        "WINEDLLOVERRIDES": DLL_OVERRIDES,
        "__COMPAT_LAYER": "RunAsInvoker",
        "XDG_RUNTIME_DIR": environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}",
    }
    if environ.get("XAUTHORITY"):
        clean["XAUTHORITY"] = environ["XAUTHORITY"]
    if any(item.id == PIPEASIO_COMPONENT for item in profile.components):
        clean["WINEDLLPATH"] = str(home / ".local" / "lib" / "wine")
    if pipeasio_debug:
        clean["PIPEASIO_DEBUG"] = "1"

    argv = [str(runner / "files" / "bin" / "wine"), str(fl64)]
    if resolved_project is not None:
        argv.append(windows_path(resolved_project))

    stamp = (now or datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    state = state_dir(environ, home)
    return LaunchSpec(
        profile=profile.name,
        argv=tuple(argv),
        env=clean,
        prefix=prefix,
        runner=runner,
        project=resolved_project,
        log_path=state / "logs" / f"{stamp}-{profile.name}-launch.log",
        pid_path=state / f"launch-{stamp}-{profile.name}.pid",
        warnings=tuple(prerequisite_warnings(prefix)),
    )


def start(spec: LaunchSpec, popen: Popen = subprocess.Popen) -> int:
    """Start FL detached in its own session; return the PID. The log and PID file go to managed state."""
    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(spec.log_path, "xb") as log:
        process = popen(
            list(spec.argv),
            env=dict(spec.env),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    pid = int(process.pid)
    spec.pid_path.write_text(f"{pid}\n", encoding="utf-8")
    return pid


def stop(profile: Profile, run: Callable[..., Any] = subprocess.run, home: Path | None = None) -> int:
    """Kill every process in the profile prefix with the runner's ``wineserver -k``; return its exit code."""
    prefix = prefix_path(profile.name)
    wineserver = runner_root(profile, home) / "files" / "bin" / "wineserver"
    env = {"HOME": str(home or Path.home()), "PATH": SAFE_PATH, "WINEPREFIX": str(prefix)}
    result = run([str(wineserver), "-k"], env=env, timeout=30, check=False)
    return int(result.returncode)


def render_spec(spec: LaunchSpec, *, dry_run: bool, running: list[int]) -> str:
    lines = [
        f"flmint launch --profile {spec.profile}" + (" --dry-run (nothing executed)" if dry_run else ""),
        f"  prefix:  {spec.prefix}",
        f"  runner:  {spec.runner}",
        f"  project: {spec.project or '(none; FL opens its default template)'}",
        "  env:",
        *(f"    {key}={value}" for key, value in sorted(spec.env.items())),
        "  argv:",
        *(f"    {arg}" for arg in spec.argv),
        f"  log:     {spec.log_path}",
    ]
    if running:
        lines.append(f"  RUNNING: prefix already in use by PIDs {', '.join(map(str, running))}")
    lines.extend(f"  warning: {item}" for item in spec.warnings)
    return "\n".join(lines)
