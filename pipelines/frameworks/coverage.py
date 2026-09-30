"""Regulatory coverage rule (plan L3 §6.2) and the expert's coverage declaration.

For each requested framework:

* ``missing`` — the framework has no control in the knowledge base;
* ``covered`` — a manifest from a source lists the expected requirements, all are
  present, ``active`` and validated (``validated_by``), and the expert declared the
  coverage (``coverage_declared_by``);
* ``partial`` — anything in between (including an unknown expected list).

A control counts for an expected requirement when its id is that requirement or when it
lists it in ``covers``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.frameworks.ingest import load_manifest, write_manifest
from pipelines.kb_candidates.kb import split_frontmatter
from pipelines.kb_candidates.owners import load_owners


def _controls(kb_dir: Path) -> dict[str, list[dict[str, Any]]]:
    by_framework: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((kb_dir / "controls").rglob("*.md")):
        if path.name.startswith("_"):
            continue
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        if not fm or not fm.get("id"):
            continue
        fw = str(fm.get("framework") or path.parent.name)
        by_framework.setdefault(fw.lower(), []).append(fm)
    return by_framework


def _framework_dir(kb_dir: Path, framework: str) -> str:
    controls = kb_dir / "controls"
    if controls.is_dir():
        for d in controls.iterdir():
            if d.is_dir() and d.name.lower() == framework.lower():
                return d.name
    return framework


def framework_coverage(framework: str, kb_dir: str | Path = "data/kb") -> dict[str, Any]:
    kb = Path(kb_dir)
    name = _framework_dir(kb, framework)
    controls = _controls(kb).get(name.lower(), [])
    manifest = load_manifest(kb, name) or {}
    expected_ids = manifest.get("expected_requirements")
    expected_list = [str(x) for x in expected_ids] if isinstance(expected_ids, list) and expected_ids else None

    by_requirement: dict[str, dict[str, Any]] = {}
    for c in controls:
        for rid in [str(c["id"])] + [str(x) for x in c.get("covers") or []]:
            by_requirement.setdefault(rid, c)

    def validated(c: dict[str, Any]) -> bool:
        return str(c.get("status")) == "active" and bool(c.get("validated_by"))

    if expected_list is not None:
        present_ids = [r for r in expected_list if r in by_requirement]
        validated_ids = [r for r in present_ids if validated(by_requirement[r])]
        missing_ids = [r for r in expected_list if r not in by_requirement]
        present, n_validated = len(present_ids), len(validated_ids)
    else:
        present = len(controls)
        n_validated = sum(1 for c in controls if validated(c))
        missing_ids = []

    declared_by = manifest.get("coverage_declared_by") or None
    if not controls:
        status = "missing"
    elif (expected_list is not None and not manifest.get("provisional") and manifest.get("source_sha256")
          and present == len(expected_list) and n_validated == len(expected_list) and declared_by):
        status = "covered"
    else:
        status = "partial"
    version = manifest.get("version") or (str(controls[0].get("version")) if controls else None)
    return {
        "status": status,
        "version": version,
        "expected": len(expected_list) if expected_list is not None else None,
        "present": present,
        "validated": n_validated,
        "missing_ids": missing_ids,
        "declared_by": declared_by,
        "provisional": bool(manifest.get("provisional")) if manifest else None,
        "manifest": bool(manifest),
    }


def compute_framework_coverage(frameworks: list[str], kb_dir: str | Path = "data/kb") -> dict[str, dict[str, Any]]:
    return {fw: framework_coverage(fw, kb_dir) for fw in frameworks if fw}


class CoverageDeclarationError(ValueError):
    pass


def declare_coverage(framework: str, by: str, kb_dir: str | Path = "data/kb") -> dict[str, Any]:
    """Record the expert's coverage declaration; refuse unless every expected requirement
    is present, active and validated, from a manifest generated from a source."""
    kb = Path(kb_dir)
    name = _framework_dir(kb, framework)
    if by not in load_owners(kb).owners:
        raise CoverageDeclarationError(f"'{by}' is not an owner declared in data/kb/owners.yaml.")
    manifest = load_manifest(kb, name)
    if not manifest:
        raise CoverageDeclarationError(f"No manifest for {name}: run 'kb ingest-framework' first.")
    if manifest.get("provisional") or not manifest.get("source_sha256"):
        raise CoverageDeclarationError(f"The {name} manifest is provisional (no ingested source): ingest the source first.")
    cov = framework_coverage(name, kb)
    if cov["expected"] is None:
        raise CoverageDeclarationError(f"The {name} manifest lists no expected requirement.")
    if cov["present"] != cov["expected"] or cov["validated"] != cov["expected"]:
        problems = []
        if cov["missing_ids"]:
            problems.append(f"missing: {cov['missing_ids']}")
        if cov["validated"] != cov["present"]:
            problems.append(f"{cov['present'] - cov['validated']} present requirement(s) not active and validated")
        raise CoverageDeclarationError(f"{name} cannot be declared covered — " + "; ".join(problems))
    manifest["coverage_declared_by"] = by
    manifest["coverage_declared_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_manifest(kb, name, manifest)
    return framework_coverage(name, kb)


def render_coverage_report(kb_dir: str | Path = "data/kb") -> str:
    """Markdown coverage report of every framework of the knowledge base (docs/COVERAGE.md)."""
    kb = Path(kb_dir)
    frameworks = sorted(d.name for d in (kb / "controls").iterdir() if d.is_dir()) if (kb / "controls").is_dir() else []
    rows, details = [], []
    for fw in frameworks:
        cov = framework_coverage(fw, kb)
        manifest = load_manifest(kb, fw) or {}
        expected = "—" if cov["expected"] is None else str(cov["expected"])
        manifest_state = "none" if not manifest else ("provisional" if manifest.get("provisional") else "from source")
        rows.append(f"| {fw} | **{cov['status']}** | {cov['version'] or '—'} | {expected} | {cov['present']} | "
                    f"{cov['validated']} | {manifest_state} | {cov['declared_by'] or '—'} |")
        if manifest:
            source = manifest.get("source") or {}
            lines = [f"### {fw} — {manifest.get('title') or fw}", ""]
            if manifest.get("source_sha256"):
                lines.append(f"- Source: `{source.get('file')}` — SHA-256 `{manifest['source_sha256']}`")
            else:
                lines.append(f"- Source: **missing** — expected: {source.get('expected') or 'n/a'}")
            if source.get("note"):
                lines.append(f"- Note: {source['note']}")
            if cov["missing_ids"]:
                shown = ", ".join(f"`{m}`" for m in cov["missing_ids"][:40])
                more = f" … (+{len(cov['missing_ids']) - 40})" if len(cov["missing_ids"]) > 40 else ""
                lines.append(f"- Missing requirements ({len(cov['missing_ids'])}): {shown}{more}")
            details.append("\n".join(lines))
    out = [
        "# Regulatory coverage of the knowledge base",
        "",
        "Generated by `poetry run kb coverage-report` (plan L3 §6.2). Status rule: **covered** requires every "
        "expected requirement of the framework manifest to be present, `active` and validated (`validated_by`), "
        "with a coverage declaration by the expert (`kb declare-coverage`); **missing** means no control in the "
        "knowledge base; anything else is **partial**. A provisional manifest (no ingested source) can never be "
        "declared covered. Nothing is declared covered by the tooling itself.",
        "",
        "| Framework | Status | Version | Expected | Present | Validated | Manifest | Declared by |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## Manifests",
        "",
        "\n\n".join(details) if details else "_No manifest._",
        "",
        "## Next steps",
        "",
        "1. Add the official sources and run `kb ingest-framework` (then `kb suggest-links`, `kb review-sheet`, "
        "`kb apply-review`) for each framework with a provisional or missing manifest.",
        "2. Existing controls predate the review cycle (`validated_by` empty): the expert validates them through "
        "`kb apply-review` (existing controls are amended in place, their curated content is kept).",
        "3. Once every expected requirement is active and validated, the expert runs `kb declare-coverage`.",
        "",
    ]
    return "\n".join(out)
