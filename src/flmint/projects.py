"""FL Studio project files: create new projects from installed templates in managed state.

FL Studio's File > Open / Save As dialog is broken under the pinned runner (Wine itemdlg custom-control
layout bug), so a brand-new untitled project cannot be saved from inside FL. The supported workflow is:
copy a template to a named path here, launch FL with that path, and save with Ctrl+S.

Writes are confined to ``<state_root>/projects`` (default ``~/.local/share/flmint/projects``). Templates are
read from the profile prefix's FL Studio install and never modified.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import FlmintError, FlmintUsageError
from .snapshots import prefix_path, state_root

DEFAULT_TEMPLATE = "Minimal/Basic with limiter"
PROJECT_SUFFIX = ".flp"


@dataclass(frozen=True)
class NewProject:
    path: Path
    template: str
    template_path: Path
    bytes: int


def projects_dir(state: Path | None = None) -> Path:
    return state_root(state) / "projects"


def fl_install_dir(prefix: Path) -> Path:
    """Locate ``Program Files/Image-Line/FL Studio <ver>`` (the directory holding FL64.exe)."""
    base = prefix / "drive_c" / "Program Files" / "Image-Line"
    candidates = sorted(path.parent for path in base.glob("FL Studio */FL64.exe"))
    if not candidates:
        raise FlmintError(
            f"no FL Studio install (FL64.exe) found under {base}",
            next_actions=("check the profile name; FL Studio must be installed in this profile's prefix",),
        )
    return candidates[-1]


def templates_root(prefix: Path) -> Path:
    return fl_install_dir(prefix) / "Data" / "Templates"


def list_templates(prefix: Path) -> list[str]:
    """Template ids as ``Category/Name`` for every ``<Category>/<Name>/<Name>.flp``."""
    root = templates_root(prefix)
    found = [
        f"{flp.parent.parent.name}/{flp.parent.name}"
        for flp in root.glob("*/*/*.flp")
        if flp.stem == flp.parent.name
    ]
    return sorted(found)


def _template_path(prefix: Path, template: str) -> Path:
    parts = template.replace("\\", "/").split("/")
    if len(parts) != 2 or any(part in {"", ".", ".."} for part in parts):
        raise FlmintUsageError(
            f"invalid template '{template}': expected 'Category/Name'",
            next_actions=("list them: flmint new-project --list-templates",),
        )
    category, name = parts
    path = templates_root(prefix) / category / name / f"{name}{PROJECT_SUFFIX}"
    if not path.is_file():
        raise FlmintUsageError(
            f"template '{template}' not found",
            next_actions=("list them: flmint new-project --list-templates",),
        )
    return path


def project_path(name: str, state: Path | None = None) -> Path:
    """Map a plain project name to ``<projects_dir>/<name>.flp``; reject anything path-like."""
    stem = name[: -len(PROJECT_SUFFIX)] if name.lower().endswith(PROJECT_SUFFIX) else name
    if (
        not stem
        or stem in {".", ".."}
        or stem.startswith(".")
        or any(sep in stem for sep in ("/", "\\", "\x00"))
    ):
        raise FlmintUsageError(
            f"invalid project name '{name}'",
            next_actions=("use a plain name such as 'my-song' (no slashes, no leading dot)",),
        )
    return projects_dir(state) / f"{stem}{PROJECT_SUFFIX}"


def new_project(
    profile: str, name: str, template: str = DEFAULT_TEMPLATE, state: Path | None = None
) -> NewProject:
    """Copy a template into managed state; never overwrite an existing project."""
    target = project_path(name, state)
    source = _template_path(prefix_path(profile, state), template)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp-{os.getpid()}"
    try:
        shutil.copyfile(source, tmp)
        tmp.chmod(0o644)
        # Atomic no-clobber publish: link() fails if the target already exists.
        os.link(tmp, target)
    except FileExistsError as exc:
        raise FlmintUsageError(
            f"project already exists: {target}",
            next_actions=("choose a new name; flmint never overwrites projects",),
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)
    return NewProject(path=target, template=template, template_path=source, bytes=target.stat().st_size)


def render_new_project(result: NewProject, profile: str) -> str:
    return "\n".join(
        (
            f"project created: {result.path} ({result.bytes} bytes)",
            f"  template: {result.template}",
            "  open it: flmint launch --profile "
            f"{profile} --project '{result.path}' --approve --no-snapshot",
            "  save with Ctrl+S only: File > Save As / Open hang under this runner (Wine itemdlg bug)",
        )
    )
