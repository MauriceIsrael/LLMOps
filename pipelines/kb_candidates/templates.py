"""Structured templates of the asset types, for a form-based authoring UI (lot L7).

Generated from ``data/kb/schema/frontmatter.schema.json``, ``EXPECTED_SECTIONS`` and, when it
exists, ``data/kb/<type>s/_template.md``. Nothing here is written to the knowledge base.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.checks import EXPECTED_SECTIONS
from pipelines.kb_candidates.kb import load_assets

ID_PREFIX = {"principle": ("P-", 3), "pattern": ("PAT-", 3), "decision": ("ADR-", 4)}
TYPE_DIR = {"principle": "principles", "pattern": "patterns", "decision": "decisions", "control": "controls"}
TYPES = (*EXPECTED_SECTIONS, "glossary")
HELP = {
    "id": "Stable identifier; leave the prefix, take the next free number.",
    "status": "Always 'draft' or 'proposed' when authoring: only a reviewed promotion makes it 'active'.",
    "confidence": "'assumed' until measured or vendor-stated evidence is attached.",
    "terms": "Keywords used by the doctrine engine to match subjects and options.",
    "assumptions": "Hypotheses under which this asset holds, one verifiable statement each (volumes, latency, "
                   "regulatory context, state of the existing system…). A reuse on another subject is confirmed "
                   "hypothesis by hypothesis: without them the asset cannot be reused.",
    "review_by": "Date by which the asset must be reviewed again (YYYY-MM-DD).",
    "checks": "Testable clauses (requires / forbids) — write them in the doctrine workshop and simulate them first.",
}


def _field(name: str, spec: dict[str, Any], required: bool) -> dict[str, Any]:
    items = spec.get("items") or {}
    return {
        "name": name,
        "required": required,
        "type": "array" if spec.get("type") == "array" else spec.get("type", "string"),
        "values": spec.get("enum") or items.get("enum"),
        "pattern": spec.get("pattern"),
        "help": HELP.get(name) or spec.get("description"),
    }


def _next_id(asset_type: str, kb_dir: Path) -> str | None:
    if asset_type not in ID_PREFIX:
        return None
    prefix, width = ID_PREFIX[asset_type]
    numbers = [int(a.id[len(prefix):]) for a in load_assets(kb_dir) if a.id.startswith(prefix) and a.id[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers, default=0) + 1):0{width}d}"


def asset_template(asset_type: str, kb_dir: str | Path = "data/kb") -> dict[str, Any] | None:
    kb = Path(kb_dir)
    if asset_type not in TYPES:
        return None
    if asset_type == "glossary":
        return {"asset_type": "glossary", "fields": [], "sections": [], "next_id": None,
                "skeleton": "**Term** — definition in one or two sentences.\n",
                "help": "A glossary candidate holds '**Term** — definition' entries (synonyms feed the doctrine engine)."}
    schema_path = kb / "schema" / "frontmatter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else {}
    required = set(schema.get("required") or ())
    fields = [_field(n, spec, n in required) for n, spec in (schema.get("properties") or {}).items()]
    for f in fields:
        if f["name"] == "type":
            f["values"] = [asset_type]
    template = kb / TYPE_DIR[asset_type] / "_template.md"
    if template.is_file():
        skeleton = template.read_text(encoding="utf-8")
    else:
        sections = "\n\n".join(f"## {s}\n" for s in EXPECTED_SECTIONS[asset_type])
        skeleton = f"---\nid: \ntitle: \ntype: {asset_type}\nstatus: draft\nconfidence: assumed\n---\n\n# Title\n\n{sections}\n"
    return {
        "asset_type": asset_type,
        "fields": fields,
        "sections": [{"heading": s, "required": True} for s in EXPECTED_SECTIONS[asset_type]],
        "next_id": _next_id(asset_type, kb),
        "skeleton": re.sub(r"\n{3,}", "\n\n", skeleton),
        "help": f"Sections marked required are checked by the 'schema' check; a {asset_type} is reviewed by the owner of its domain.",
    }
