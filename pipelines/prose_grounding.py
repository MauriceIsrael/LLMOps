"""Grounded drafts for ``POST /api/prose/suggest-batch`` (assistance of the Document Engine prose blocks, ADR-DE-02).

The hub provides KNOWLEDGE, not a narrative: a draft lists the doctrine of the knowledge base that applies to the block, each
item with its identifier, type, confidence and an excerpt. It never states that the project's design is validated or
compliant (the hub does not know the project), never invents a sentence, and returns NO draft (a warning instead) when
nothing applies. A false provenance is worse than no draft: the author sees the draft as an assisted suggestion and may
believe what it says.

Confidence is kept as the knowledge base publishes it; ``vendor-stated`` and ``assumed`` are never presented as verified
(suite epistemic mapping).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

HEADER = (
    "Connaissances de la base applicables à ce bloc — à reformuler et à valider par l'auteur ; "
    "elles ne démontrent pas que la conception du projet s'y conforme :"
)
CONFIDENCE_LABELS = {
    "verified": "vérifié",
    "designed": "conçu, à valider",
    "vendor-stated": "déclaration constructeur, non vérifiée",
    "stated-by-client": "déclaré par le client, non vérifié",
    "assumed": "hypothèse",
}
TYPE_LABELS = {"principle": "principe", "pattern": "motif", "decision": "décision", "control": "contrôle"}
DoctrineFn = Callable[..., dict[str, Any]]


def _labels(context: Any) -> list[str]:
    items = context.get("anchoredItems") if isinstance(context, dict) else None
    out: list[str] = []
    for item in items if isinstance(items, list) else []:
        label = (item.get("attributes") or {}).get("label") if isinstance(item, dict) else None
        if isinstance(label, str) and label.strip():
            out.append(label.strip())
    return out


def ground_block(request: dict[str, Any], doctrine: DoctrineFn, *, max_items: int = 5, max_chars: int = 1500) -> tuple[str | None, str | None]:
    """``(draft, None)`` when knowledge applies, else ``(None, reason)``. ``doctrine`` is ``get_doctrine_context``."""
    raw_instructions = request.get("instructions")
    instructions = raw_instructions if isinstance(raw_instructions, str) else ""
    labels = _labels(request.get("context"))
    subject = ". ".join([*labels, instructions.strip()]).strip(". ").strip()
    if not subject:
        return None, "Aucun libellé d'élément ancré ni consigne : rien à confronter à la base de connaissances."
    result = doctrine(subject=subject, max_items=max_items, max_chars=max_chars)
    data = result.get("data") if isinstance(result, dict) and result.get("status") == "ok" else None
    items = data.get("items") if isinstance(data, dict) else None
    if not items:
        return None, f"Aucune connaissance applicable trouvée dans la base pour « {subject[:80]} »."
    lines = [HEADER]
    for it in items:
        confidence = str(it.get("confidence") or "")
        qualifier = CONFIDENCE_LABELS.get(confidence, confidence or "confiance non renseignée")
        kind = TYPE_LABELS.get(str(it.get("type")), str(it.get("type") or "actif"))
        excerpt = " ".join(str(it.get("excerpt") or "").split())
        lines.append(f"- [{it.get('id')}] {it.get('title')} ({kind}, {qualifier}) : {excerpt}".rstrip(" :"))
    return "\n".join(lines), None
