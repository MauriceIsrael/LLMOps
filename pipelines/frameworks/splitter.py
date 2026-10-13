"""Deterministic splitting of a regulatory source into requirement units.

A splitter is configured per framework in ``pipelines/frameworks/splitters/<fw>.yaml``:

* ``mode: structured`` — hierarchical text (article / paragraph / point). Each level
  has a regular expression; a paragraph with points yields one unit per point, a
  paragraph without points yields one unit.
* ``mode: tagged`` — requirements carrying their own tag (e.g. ``[R-5.1.1-001]``).

Options of the structured mode, for the layout of official texts (EUR-Lex HTML puts a point
label such as ``(a)`` on its own line):

* ``sequential: true`` on a level — a new unit of that level must follow the previous one
  (``1`` -> ``2``, ``a`` -> ``b``; the first one is free). Other matches are ordinary text:
  roman sub-points ``(i)`` after ``(d)``, cross-reference tables at the end of a text.
* ``inline`` — units (given by all their parts, e.g. ``{article: "23", paragraph: "4"}``)
  whose child points stay in their text instead of becoming units.
* ``exclude`` — units dropped (same form; a unit matches when all the given parts are equal).
* ``stop`` — patterns of heading lines (``^CHAPTER [IVX]+$``, ``^Section [0-9]+$``) that end the
  current unit, so they are not appended to the last paragraph of a chapter or section.
* An article without numbered paragraphs is one unit (unused id separators are trimmed).
* ``structures`` — several structures in one source (e.g. articles and an annex): a list of
  structured configurations (``levels``, ``id_template``, ``ref_template``, ``include``...)
  whose units are concatenated; keys missing in a structure are taken from the file.

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
    inline: list[dict[str, str]] = field(default_factory=list)
    exclude: list[dict[str, str]] = field(default_factory=list)
    structures: list[SplitterConfig] = field(default_factory=list)
    stop: list[str] = field(default_factory=list)


def _part_specs(value: Any) -> list[dict[str, str]]:
    return [{str(k): str(v) for k, v in (spec or {}).items()} for spec in value or []]


def _structure(raw: dict[str, Any], base: dict[str, Any], framework: str) -> SplitterConfig:
    """Configuration of one structure; keys missing in ``raw`` are taken from ``base`` (the file)."""
    def get(key: str) -> Any:
        return raw.get(key, base.get(key))

    return SplitterConfig(
        framework=str(get("framework") or framework),
        title=str(get("title") or framework),
        mode=str(get("mode") or "structured"),
        id_template=str(get("id_template") or ""),
        ref_template=str(get("ref_template") or "{ref}"),
        levels=list(get("levels") or []),
        requirement=dict(get("requirement") or {}),
        include={k: [str(x) for x in v] for k, v in (get("include") or {}).items()},
        defaults=dict(get("defaults") or {}),
        jurisdiction=str(get("jurisdiction") or ""),
        raw=raw,
        inline=_part_specs(get("inline")),
        exclude=_part_specs(get("exclude")),
        stop=[str(x) for x in get("stop") or []],
    )


def load_splitter(framework: str, path: str | Path | None = None) -> SplitterConfig:
    """Splitter configuration of a framework (``splitters/<framework lower>.yaml`` by default)."""
    cfg_path = Path(path) if path else SPLITTERS_DIR / f"{framework.lower()}.yaml"
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"No splitter configuration for '{framework}' ({cfg_path}); write one in pipelines/frameworks/splitters/."
        )
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not raw.get("structures") and not raw.get("id_template"):
        raise ValueError(f"{cfg_path}: 'id_template' (or 'structures') is required.")
    cfg = _structure(raw, {}, framework)
    shared = {k: v for k, v in raw.items() if k != "structures"}
    cfg.structures = [_structure(dict(st), shared, framework) for st in raw.get("structures") or []]
    if cfg.structures and not cfg.id_template:
        cfg.id_template = " ".join(st.id_template for st in cfg.structures)  # e.g. to detect '{tag}'
    return cfg


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


def _matches(spec: dict[str, str], parts: dict[str, str]) -> bool:
    return all(parts.get(k, "") == v for k, v in spec.items())


def _included(cfg: SplitterConfig, parts: dict[str, str]) -> bool:
    if any(_matches(spec, parts) for spec in cfg.exclude):
        return False
    return all(parts.get(level, "") in allowed for level, allowed in cfg.include.items())


def _successor(value: str) -> str:
    if value.isdigit():
        return str(int(value) + 1)
    if len(value) == 1 and value.isalpha():
        return chr(ord(value) + 1)
    return ""


def _unit_id(template: str, parts: dict[str, str]) -> str:
    return re.sub(r"[-_.]+$", "", _format(template, parts))


def split_structured(text: str, cfg: SplitterConfig, tag: str = "") -> list[Requirement]:
    levels = [(lvl["name"], re.compile(lvl["pattern"])) for lvl in cfg.levels]
    title_levels = {lvl["name"] for lvl in cfg.levels if lvl.get("title_next_line")}
    sequential = {lvl["name"] for lvl in cfg.levels if lvl.get("sequential")}
    names = [n for n, _ in levels]
    last: dict[str, str] = {}  # last value per sequential level (reset with its parent)
    stops = [re.compile(x) for x in cfg.stop]
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
                    id=_unit_id(cfg.id_template, p),
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
        if any(st.match(line) for st in stops):
            flush()
            parts.clear()
            intro.clear()
            continue
        matched = False
        for depth, (name, pattern) in enumerate(levels):
            m = pattern.match(line)
            if not m:
                continue
            num = m.group("num")
            if name in sequential and name in last and num != _successor(last[name]):
                continue  # not the next unit of this level: ordinary text
            if current and depth > 0 and names.index(current["level"]) < depth and any(
                    _matches(spec, current["parts"]) and len(spec) == len(current["parts"]) for spec in cfg.inline):
                last[name] = num
                break  # child of an inline unit: stays in its text
            matched = True
            if current and current["level"] != name and names.index(current["level"]) < depth:
                # A child starts: the pending parent text becomes the children's context.
                intro[name] = current["text"]
                current = None
            else:
                flush()
            parts[name] = num
            last[name] = num
            for deeper in names[depth + 1:]:
                parts.pop(deeper, None)
                intro.pop(deeper, None)
                last.pop(deeper, None)
            if depth == 0:
                headings[name] = ""
                intro.clear()
                if name in title_levels:
                    expect_title = name
            unit_text = m.groupdict().get("text") or ""
            if depth > 0 or unit_text:
                current = {"level": name, "parts": {k: parts[k] for k in names if k in parts}, "text": unit_text}
            break
        if not matched:
            if current is not None:
                current["text"] += " " + line
            elif names and list(parts) == names[:1]:
                # Body of an article without numbered paragraphs: the article is the unit.
                current = {"level": names[0], "parts": dict(parts), "text": line}
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
    if cfg.structures:
        return _dedupe([u for structure in cfg.structures for u in split(text, structure, tag)])
    if cfg.mode == "tagged":
        return split_tagged(text, cfg, tag)
    if cfg.mode == "structured":
        return split_structured(text, cfg, tag)
    raise ValueError(f"Unknown splitter mode '{cfg.mode}'")
