"""Profile/manifest schema with a dependency-free YAML-subset loader (stdlib only).

Supports the constrained YAML used by profiles/*.yaml: nested mappings, lists of
mappings/scalars, quoted/plain scalars, ints/floats/bools/nulls, full-line comments.
Tabs, anchors, flow collections ([{...}]), and multi-document files are rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ManifestError

COMPONENT_KINDS = {"flatpak", "download", "build"}
GATE_KINDS = {"pipewire_min"}
COMPONENT_KEYS = {
    "id",
    "kind",
    "name",
    "version",
    "source_url",
    "download_url",
    "asset",
    "size_bytes",
    "sha256",
    "license",
    "notes",
}
_PROFILE_KEYS = {
    "name",
    "title",
    "description",
    "components",
    "gates",
    "installer_required",
    "min_disk_mib",
    "human_checklist",
}

_TOK_RE = re.compile(r"^( *)(.*)$")
_KEY_RE = re.compile(r"^([A-Za-z0-9_.\-]+):(?:\s+(.*))?$")
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")
_VERSION_TUPLE_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class _Tok:
    indent: int
    text: str
    lineno: int


def _strip_comment(raw: str) -> str:
    stripped = raw.lstrip(" ")
    if stripped.startswith("#"):
        return ""
    cut = re.search(r"\s+#", raw)
    return raw[: cut.start()] if cut else raw


def _tokenize(text: str, source: str) -> list[_Tok]:
    toks: list[_Tok] = []
    for lineno, raw in enumerate((text or "").splitlines(), start=1):
        content = _strip_comment(raw.rstrip())
        if not content.strip():
            continue
        if "\t" in content[: len(content) - len(content.lstrip())]:
            raise ManifestError(
                f"{source}:{lineno}: tab indentation is not supported",
                next_actions=("re-indent with spaces",),
            )
        match = _TOK_RE.match(content)
        assert match is not None
        toks.append(_Tok(len(match.group(1)), match.group(2).strip(), lineno))
    return toks


def _scalar(text: str, source: str, lineno: int) -> Any:
    if text == "":
        return None
    if text[0] in {'"', "'"}:
        if len(text) < 2 or text[-1] != text[0]:
            raise ManifestError(
                f"{source}:{lineno}: unterminated quoted scalar", next_actions=("close the quote",)
            )
        return text[1:-1]
    lowered = text.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    return text


def _parse_block(toks: list[_Tok], i: int, indent: int, source: str) -> tuple[Any, int]:
    if i >= len(toks):
        return None, i
    if toks[i].text.startswith("- ") or toks[i].text == "-":
        return _parse_list(toks, i, indent, source)
    return _parse_map(toks, i, indent, source)


def _parse_map(toks: list[_Tok], i: int, indent: int, source: str) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while i < len(toks) and toks[i].indent == indent and not toks[i].text.startswith("- "):
        tok = toks[i]
        match = _KEY_RE.match(tok.text)
        if match is None:
            raise ManifestError(
                f"{source}:{tok.lineno}: expected 'key: value' or 'key:'",
                next_actions=("check the profile syntax",),
            )
        key, rest = match.group(1), (match.group(2) or "").strip()
        i += 1
        if rest:
            result[key] = _scalar(rest, source, tok.lineno)
        elif i < len(toks) and toks[i].indent > indent:
            child, i = _parse_block(toks, i, toks[i].indent, source)
            result[key] = child
        elif i < len(toks) and toks[i].indent == indent and toks[i].text.startswith("- "):
            child, i = _parse_block(toks, i, indent, source)
            result[key] = child
        else:
            result[key] = None
    return result, i


def _parse_list(toks: list[_Tok], i: int, indent: int, source: str) -> tuple[list[Any], int]:
    items: list[Any] = []
    while i < len(toks) and toks[i].indent == indent and toks[i].text.startswith("-"):
        tok = toks[i]
        rest = tok.text[1:].strip()
        if not rest:
            i += 1
            if i < len(toks) and toks[i].indent > indent:
                child, i = _parse_block(toks, i, toks[i].indent, source)
                items.append(child)
            else:
                items.append(None)
        elif _KEY_RE.match(rest):
            virtual = toks[:i] + [_Tok(indent + 2, rest, tok.lineno)] + toks[i + 1 :]
            child, i = _parse_block(virtual, i, indent + 2, source)
            items.append(child)
        else:
            items.append(_scalar(rest, source, tok.lineno))
            i += 1
    return items, i


def load_yaml_subset(text: str, source: str = "<text>") -> Any:
    toks = _tokenize(text, source)
    if not toks:
        return {}
    value, consumed = _parse_block(toks, 0, toks[0].indent, source)
    if consumed != len(toks):
        bad = toks[consumed]
        raise ManifestError(
            f"{source}:{bad.lineno}: inconsistent indentation",
            next_actions=("align this line with the enclosing block",),
        )
    return value


@dataclass(frozen=True)
class Component:
    id: str
    kind: str
    name: str
    version: str | None
    source_url: str | None
    sha256: str | None
    license: str | None
    notes: str | None
    download_url: str | None = None
    asset: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class Gate:
    id: str
    kind: str
    min_version: tuple[int, int, int] | None
    applies_to: str | None


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    description: str
    components: tuple[Component, ...]
    gates: tuple[Gate, ...]
    installer_required: bool
    min_disk_mib: int
    human_checklist: tuple[str, ...]
    source_file: str


def parse_version_tuple(value: Any) -> tuple[int, int, int] | None:
    if isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) for v in value):
        return (value[0], value[1], value[2])
    if isinstance(value, str):
        match = _VERSION_TUPLE_RE.match(value.strip())
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def _known_keys(raw: dict[str, Any], problems: list[str]) -> None:
    for key in raw:
        if key not in _PROFILE_KEYS:
            problems.append(f"unknown profile key '{key}'")


def _coerce_list(value: Any, key: str, problems: list[str]) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    problems.append(f"'{key}' must be a list")
    return []


def _str_or_none(entry: dict[str, Any], key: str) -> str | None:
    value = entry.get(key)
    return value if isinstance(value, str) else None


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", value))


def _download_url_or_none(entry: dict[str, Any], label: str, index: int, problems: list[str]) -> str | None:
    value = entry.get("download_url")
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("https://"):
        problems.append(f"components[{index}] ({label}): download_url must be an https:// URL")
        return None
    return value


def _asset_or_none(entry: dict[str, Any], label: str, index: int, problems: list[str]) -> str | None:
    value = entry.get("asset")
    if value is None:
        return None
    if not isinstance(value, str) or not value or "/" in value or ".." in value:
        problems.append(
            f"components[{index}] ({label}): asset must be a single filename without path separators"
        )
        return None
    return value


def _size_or_none(entry: dict[str, Any], label: str, index: int, problems: list[str]) -> int | None:
    value = entry.get("size_bytes")
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        problems.append(f"components[{index}] ({label}): size_bytes must be a positive integer")
        return None
    return value


def _component_from_raw(entry: Any, index: int, problems: list[str]) -> Component | None:
    if not isinstance(entry, dict):
        problems.append(f"components[{index}] must be a mapping")
        return None

    cid = entry.get("id")
    kind = entry.get("kind")
    if not isinstance(cid, str) or not cid.strip():
        problems.append(f"components[{index}]: required string 'id' missing")
        return None
    if not isinstance(kind, str) or kind not in COMPONENT_KINDS:
        problems.append(f"components[{index}] ({cid}): kind must be in {sorted(COMPONENT_KINDS)}")
        return None
    label = str(cid)
    for key in entry:
        if key not in COMPONENT_KEYS:
            problems.append(f"components[{index}] ({label}): unknown component key '{key}'")

    sha256 = entry.get("sha256")
    if sha256 is not None and not _valid_sha256(sha256):
        problems.append(f"components[{index}] ({label}): sha256 must be 64 hex digits or null")

    version = entry.get("version")
    if isinstance(version, int | float):
        version = str(version)

    return Component(
        id=cid.strip(),
        kind=kind,
        name=str(entry.get("name") or cid).strip(),
        version=version if version is None else str(version),
        source_url=_str_or_none(entry, "source_url"),
        sha256=sha256 if isinstance(sha256, str) else None,
        license=_str_or_none(entry, "license"),
        notes=_str_or_none(entry, "notes"),
        download_url=_download_url_or_none(entry, label, index, problems),
        asset=_asset_or_none(entry, label, index, problems),
        size_bytes=_size_or_none(entry, label, index, problems),
    )


def _components_from_raw(raw: dict[str, Any], problems: list[str]) -> list[Component]:
    components: list[Component] = []
    entries = _coerce_list(raw.get("components"), "components", problems)
    for index, entry in enumerate(entries):
        component = _component_from_raw(entry, index, problems)
        if component is not None:
            components.append(component)
    return components


def _gate_from_raw(
    entry: Any,
    index: int,
    component_ids: set[str],
    problems: list[str],
) -> Gate | None:
    if not isinstance(entry, dict):
        problems.append(f"gates[{index}] must be a mapping")
        return None

    gid = entry.get("id")
    kind = entry.get("kind")
    if not isinstance(gid, str) or not gid.strip():
        problems.append(f"gates[{index}]: required string 'id' missing")
        return None
    if not isinstance(kind, str) or kind not in GATE_KINDS:
        problems.append(f"gates[{index}] ({gid}): kind must be in {sorted(GATE_KINDS)}")
        return None

    min_version = None
    if kind == "pipewire_min":
        min_version = parse_version_tuple(entry.get("min_version"))
        if min_version is None:
            problems.append(f"gates[{index}] ({gid}): pipewire_min needs min_version like 1.4.2")

    applies_to = entry.get("applies_to")
    applies_to_text = str(applies_to) if applies_to else None
    if applies_to_text is not None and applies_to_text not in component_ids:
        problems.append(
            f"gates[{index}] ({gid}): applies_to references unknown component '{applies_to_text}'"
        )

    return Gate(
        id=gid.strip(),
        kind=kind,
        min_version=min_version,
        applies_to=applies_to_text,
    )


def _gates_from_raw(raw: dict[str, Any], components: list[Component], problems: list[str]) -> list[Gate]:
    gates: list[Gate] = []
    component_ids = {c.id for c in components}
    entries = _coerce_list(raw.get("gates"), "gates", problems)
    for index, entry in enumerate(entries):
        gate = _gate_from_raw(entry, index, component_ids, problems)
        if gate is not None:
            gates.append(gate)
    return gates


def _validate_scalars(raw: dict[str, Any], problems: list[str]) -> tuple[bool, int]:
    installer_required = raw.get("installer_required", True)
    if not isinstance(installer_required, bool):
        problems.append("'installer_required' must be true/false")
        installer_required = True

    min_disk_mib = raw.get("min_disk_mib", 12288)
    if not isinstance(min_disk_mib, int) or isinstance(min_disk_mib, bool) or min_disk_mib < 0:
        problems.append("'min_disk_mib' must be a non-negative integer")
        min_disk_mib = 12288

    return bool(installer_required), int(min_disk_mib)


def _checklist_from_raw(raw: dict[str, Any], problems: list[str]) -> list[str]:
    checklist: list[str] = []
    entries = _coerce_list(raw.get("human_checklist"), "human_checklist", problems)
    for item in entries:
        if isinstance(item, str):
            checklist.append(item)
        else:
            problems.append("human_checklist entries must be strings")
    return checklist


def load_profile_text(text: str, source: str) -> Profile:
    raw = load_yaml_subset(text, source)
    if not isinstance(raw, dict):
        raise ManifestError(
            f"{source}: profile must be a mapping",
            next_actions=("fix the profile file",),
        )

    problems: list[str] = []
    name_value = raw.get("name")
    if not isinstance(name_value, str) or not name_value.strip():
        problems.append("missing required string key 'name'")
        name = "profile"
    else:
        name = name_value.strip()

    _known_keys(raw, problems)
    components = _components_from_raw(raw, problems)
    gates = _gates_from_raw(raw, components, problems)
    installer_required, min_disk_mib = _validate_scalars(raw, problems)
    checklist = _checklist_from_raw(raw, problems)

    if problems:
        raise ManifestError(
            f"invalid profile {source}: " + "; ".join(problems),
            next_actions=(
                "fix the profile YAML and re-run",
                "compare with profiles/stable.example.yaml",
            ),
        )

    return Profile(
        name=name,
        title=str(raw.get("title") or name),
        description=str(raw.get("description") or ""),
        components=tuple(components),
        gates=tuple(gates),
        installer_required=installer_required,
        min_disk_mib=min_disk_mib,
        human_checklist=tuple(checklist),
        source_file=source,
    )


def load_profile_file(path: Path) -> Profile:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(
            f"cannot read profile {path}: {exc.strerror or exc}",
            next_actions=("check the profile path", "see profiles/*.example.yaml"),
        ) from exc
    return load_profile_text(text, str(path))
