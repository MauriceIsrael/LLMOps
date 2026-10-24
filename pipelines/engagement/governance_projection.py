"""Projection « décision du Hub → ``governanceStatements`` du Document Engine » (#153, ADR-DE-44).

Projection **de référence**, pure et déterministe, qui dit comment une décision de l'instantané d'engagement (K16) devient ce que le
Document Engine lit : un ``ProjectedGovernanceStatement`` (``id``, ``name``, ``governanceKind``, ``description``, ``attributes``). Le
propriétaire de l'adaptateur reste à désigner (A20, #40) : ce module fixe la **correspondance**, il ne décide pas qui la porte. Le contrat
lisible est ``docs/contracts/suite-governance-projection.md``.

Règles (chacune a un test) :

* Seul un instantané **vérifié** est projeté (``verify`` du canal K11) : on ne projette pas ce que le Hub refuserait d'émettre.
* Une décision **proposée** ne sort jamais comme un fait : par défaut elle n'est pas publiée ; avec ``include_proposed`` elle l'est,
  marquée ``decision-status: proposed``. Une décision remplacée ou retirée n'engage plus personne : jamais publiée.
* Un statut que cette projection ne connaît pas **lève** : on ne devine pas.
* Toutes les valeurs d'``attributes`` sont des chaînes (``Record<string, string>``) ; les noms sont ceux du métamodèle du producteur
  (ADR-DE-44 §3), ici le Hub : jamais renommés en chemin.
* Le Hub ne détient **ni hypothèses ni risques** : cette projection n'en publie aucun et le dit dans son rapport. Un plan de document
  alimenté par le Hub ne doit donc pas porter de registre de risques (un registre vide se lirait « aucun risque »).
"""

from __future__ import annotations

import json
from typing import Any

from pipelines.engagement.snapshot import verify

# Vocabulaire de `decision-status` constaté dans le catalogue d'Architecture Studio lu par le Document Engine (`accepted`, `proposed`).
# Les autres valeurs que ce vocabulaire pourrait porter ne sont pas connues du Hub : elles ne sont pas inventées ici.
PROJECTED_STATUS = {"active": "accepted", "proposed": "proposed"}
NEVER_PUBLISHED = ("superseded", "withdrawn")


class ProjectionRefusedError(ValueError):
    """L'instantané n'est pas projetable (non vérifié, ou statut inconnu) : rien n'est produit."""


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _statement(engagement: str, decision: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
    attributes: dict[str, str] = {
        "governance-kind": "decision",
        "decision-status": PROJECTED_STATUS[decision["status"]],
        "assertion-level": decision["assertion_level"],
        "origin": decision["origin"],
        "subject": decision["subject"],
        "reversibility": decision["reversibility"],
        "source": "knowledge-hub",
        "source-snapshot": snapshot_id,
    }
    if decision.get("validated_by"):
        attributes["validated-by"] = decision["validated_by"]
        attributes["validated-at"] = decision["validated_at"]
    rejected = "; ".join(f"{r['option']} — {r['reason']}" for r in decision.get("rejected") or [])
    consequences = "; ".join(decision.get("consequences") or [])
    violations = "; ".join(f"{v['typed_id']} — {v['justification']}" for v in decision.get("accepted_violations") or [])
    based_on = ", ".join(b["id"] for b in decision.get("based_on") or [])
    facts = "; ".join(f"{f['key']}={_text(f['value'])}" for f in decision.get("facts") or [])
    # Une propriété absente rend une cellule vide : « cette décision ne porte pas cette propriété » (ADR-DE-44), jamais « aucune ».
    for name, value in (("rejected-options", rejected), ("consequences", consequences), ("accepted-violations", violations),
                        ("based-on", based_on), ("facts", facts)):
        if value:
            attributes[name] = value
    return {
        "id": f"{engagement}:{decision['id']}",
        "name": decision["decision"],
        "governanceKind": "decision",
        "description": decision.get("rationale") or "",
        "attributes": attributes,
    }


def project_decisions(envelope: dict[str, Any], *, include_proposed: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retourne ``(governanceStatements, rapport)`` pour un instantané d'engagement scellé du Hub."""
    problems = verify(envelope)
    if problems:
        raise ProjectionRefusedError(f"instantané non vérifié ({len(problems)} problème(s), le premier : {problems[0].code})")
    data = envelope["data"]
    engagement = data["engagement"]["id"]
    excluded = {"proposed": 0, "superseded": 0, "withdrawn": 0}
    statements: list[dict[str, Any]] = []
    for decision in sorted(data.get("decisions") or [], key=lambda d: d["id"]):
        status = decision["status"]
        if status in NEVER_PUBLISHED:
            excluded[status] += 1
            continue
        if status not in PROJECTED_STATUS:
            raise ProjectionRefusedError(f"statut de décision inconnu : {status!r} (décision {decision['id']})")
        if status == "proposed" and not include_proposed:
            excluded["proposed"] += 1
            continue
        statements.append(_statement(engagement, decision, envelope["snapshotId"]))
    report = {
        "engagement": engagement,
        "snapshot_id": envelope["snapshotId"],
        "snapshot_checksum": envelope["checksum"],
        "is_provisional": data["is_provisional"],
        "provisional_reasons": data["provisional_reasons"],
        "published": len(statements),
        "excluded": excluded,
        "not_published_by_the_hub": ["assumption", "risk"],
    }
    return statements, report
