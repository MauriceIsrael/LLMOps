"""Deterministic splitting of a regulatory source into requirement units.

A splitter is configured per framework in ``pipelines/frameworks/splitters/<fw>.yaml``:

* ``mode: structured`` — hierarchical text (article / paragraph / point). Each level
  has a regular expression; a paragraph with points yields one unit per point, a
  paragraph without points yields one unit.
* ``mode: tagged`` — requirements carrying their own tag (e.g. ``[R-5.1.1-001]``).

The unit identifier comes from ``id_template`` (e.g. ``NIS2-ART{article}-{paragraph}{point}``);
the legal text is kept verbatim (lines joined with single spaces).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SPLITTERS_DIR = Path(__file__).parent / "splitters"


@dataclass
class Requirement:
    id: str
    ref: str
    title: str
    text: str
    context: str = ""
    parts: dict[str, str] = field(default_factory=dict)


@dataclass
class SplitterConfig:
    framework: str
    title: str
    mode: str
    id_template: str
    ref_template: str
    levels: list[dict[str, Any]]
    requirement: dict[str, Any]
    include: dict[str, list[str]]
    defaults: dict[str, Any]
    jurisdiction: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def load_splitter(framework: str, path: str | Path | None = None) -> SplitterConfig:
    """Splitter configuration of a framework (``splitters/<framework lower>.yaml`` by default)."""
    cfg_path = Path(path) if path else SPLITTERS_DIR / f"{framework.lower()}.yaml"
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"No splitter configuration for '{framework}' ({cfg_path}); write one in pipelines/frameworks/splitters/."
        )
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return SplitterConfig(
        framework=str(raw.get("framework") or framework),
        title=str(raw.get("title") or framework),
        mode=str(raw.get("mode") or "structured"),
        id_template=str(raw["id_template"]),
        ref_template=str(raw.get("ref_template") or "{ref}"),
        levels=list(raw.get("levels") or []),
        requirement=dict(raw.get("requirement") or {}),
        include={k: [str(x) for x in v] for k, v in (raw.get("include") or {}).items()},
        defaults=dict(raw.get("defaults") or {}),
        jurisdiction=str(raw.get("jurisdiction") or ""),
        raw=raw,
    )


def _format(template: str, parts: dict[str, str]) -> str:
    values = {k: v for k, v in parts.items()}
    values.setdefault("point", "")
    values["point_upper"] = values.get("point", "").upper()
    values["point_paren"] = f"({values['point']})" if values.get("point") else ""
    values["paragraph_paren"] = f"({values['paragraph']})" if values.get("paragraph") else ""
    return template.format_map(_Default(values))


class _Default(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _title(text: str, heading: str, limit: int = 90) -> str:
    sentence = re.split(r"(?<=[.;:])\s", text.strip(), maxsplit=1)[0].rstrip(";:,.")
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rsplit(" ", 1)[0] + "…"
    return f"{heading} — {sentence}" if heading else sentence


def _included(cfg: SplitterConfig, parts: dict[str, str]) -> bool:
    return all(parts.get(level, "") in allowed for level, allowed in cfg.include.items())


def split_structured(text: str, cfg: SplitterConfig, tag: str = "") -> list[Requirement]:
    levels = [(lvl["name"], re.compile(lvl["pattern"])) for lvl in cfg.levels]
    title_levels = {lvl["name"] for lvl in cfg.levels if lvl.get("title_next_line")}
    names = [n for n, _ in levels]
    parts: dict[str, str] = {}
    headings: dict[str, str] = {}
    units: list[Requirement] = []
    current: dict[str, Any] | None = None  # unit being accumulated
    intro: dict[str, str] = {}  # text of a parent level whose children are units
    expect_title: str | None = None

    def flush() -> None:
        nonlocal current
        if current and current["text"].strip():
            p = dict(current["parts"])
            if _included(cfg, p):
                p["tag"] = tag
                body = " ".join(current["text"].split())
                heading = headings.get(names[0], "")
                units.append(Requirement(
                    id=_format(cfg.id_template, p),
                    ref=_format(cfg.ref_template, p),
                    title=_title(body, heading),
                    text=body,
                    context=" ".join(intro.get(current["level"], "").split()),
                    parts=p,
                ))
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if expect_title:
            headings[expect_title] = line
            expect_title = None
            continue
        matched = False
        for depth, (name, pattern) in enumerate(levels):
            m = pattern.match(line)
            if not m:
                continue
            matched = True
            if current and current["level"] != name and names.index(current["level"]) < depth:
                # A child starts: the pending parent text becomes the children's context.
                intro[name] = current["text"]
                current = None
            else:
                flush()
            parts[name] = m.group("num")
            for deeper in names[depth + 1:]:
                parts.pop(deeper, None)
                intro.pop(deeper, None)
            if depth == 0:
                headings[name] = ""
                intro.clear()
                if name in title_levels:
                    expect_title = name
            unit_text = m.groupdict().get("text") or ""
            if depth > 0 or unit_text:
                current = {"level": name, "parts": {k: parts[k] for k in names if k in parts}, "text": unit_text}
            break
        if not matched and current is not None:
            current["text"] += " " + line
    flush()
    return _dedupe(units)


def split_tagged(text: str, cfg: SplitterConfig, tag: str = "") -> list[Requirement]:
    pattern = re.compile(cfg.requirement["pattern"])
    units: list[Requirement] = []
    current: Requirement | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        m = pattern.match(line)
        if m:
            if current:
                units.append(current)
            p = {k: v for k, v in m.groupdict().items() if k != "text" and v is not None}
            p["tag"] = tag
            body = m.group("text").strip()
            current = Requirement(id=_format(cfg.id_template, p), ref=_format(cfg.ref_template, p),
                                  title=_title(body, ""), text=body, parts=p)
        elif current and line and not line.startswith(("[", "NOTE")) and not re.match(r"^\d+(\.\d+)*\s", line):
            current.text += " " + line
    if current:
        units.append(current)
    for u in units:
        u.text = " ".join(u.text.split())
        u.title = _title(u.text, "")
    return _dedupe([u for u in units if _included(cfg, u.parts)])


def _dedupe(units: list[Requirement]) -> list[Requirement]:
    seen: dict[str, Requirement] = {}
    for u in units:
        seen.setdefault(u.id, u)
    return list(seen.values())


def split(text: str, cfg: SplitterConfig, tag: str = "") -> list[Requirement]:
    """Requirement units of a source text, in document order, one per identifier."""
    if cfg.mode == "tagged":
        return split_tagged(text, cfg, tag)
    if cfg.mode == "structured":
        return split_structured(text, cfg, tag)
    raise ValueError(f"Unknown splitter mode '{cfg.mode}'")
