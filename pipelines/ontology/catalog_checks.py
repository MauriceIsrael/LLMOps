"""Contrôles de cohérence du catalogue d'ontologie servi (issues #190 et #191).

Deux familles, appliquées à la forme « catalogue » (``entities``) :

1. **Cohérence interne d'une feuille** : une feuille qui déclare des ``oracle_rules`` doit fournir les ``projections``
   (paramètres des règles) ; des ``projections`` doivent être justifiées par des ``governed_by_clauses``.
2. **Pureté d'intention** : l'ontologie est une doctrine d'entreprise partagée par tous les projets ; elle ne porte pas de
   valeur d'INSTANCIATION (adresse IPv4/IPv6, CIDR, adresse MAC). Contrôlé dans les ``projections`` (paramètres de règles) et
   dans le modèle de graphe ``hydration_template.reconciliation_graph``. Les autres gabarits d'hydratation génèrent par
   nature des valeurs par défaut et ne sont pas contrôlés ici.

Les instances concrètes (identifiants, tenants, sous-réseaux) sont une donnée du PROJET, jamais de l'ontologie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w.])")
_MAC = re.compile(r"(?<![\w:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![\w:-])")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}(?:/\d{1,3})?(?![\w:])")

# Valeurs génériques qui ne désignent aucune instance.
_ALLOWED_LITERALS = frozenset({"0.0.0.0", "0.0.0.0/0", "255.255.255.255", "::", "::/0"})


@dataclass(frozen=True)
class CatalogFinding:
    code: str
    severity: str
    urn: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "urn": self.urn, "path": self.path, "message": self.message}


def _instantiation_values(value: Any, path: str) -> list[tuple[str, str, str]]:
    """Parcourt une valeur JSON et renvoie (chemin, nature, valeur) pour chaque valeur d'instanciation."""
    found: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for k, v in value.items():
            found.extend(_instantiation_values(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found.extend(_instantiation_values(v, f"{path}[{i}]"))
    elif isinstance(value, str):
        for rx, kind in ((_IPV4, "ipv4"), (_MAC, "mac"), (_IPV6, "ipv6")):
            for m in rx.finditer(value):
                if m.group(0) not in _ALLOWED_LITERALS:
                    found.append((path, kind, m.group(0)))
    return found


def check_leaf_coherence(entities: dict[str, Any]) -> list[CatalogFinding]:
    """Règles ↔ paramètres ↔ clauses, feuille par feuille."""
    findings: list[CatalogFinding] = []
    for urn, e in sorted(entities.items()):
        if e.get("kind") != "leaf":
            continue
        rules = e.get("oracle_rules") or []
        projections = e.get("projections") or {}
        if rules and not projections:
            findings.append(
                CatalogFinding(
                    "oracle_rules_without_projections",
                    SEVERITY_ERROR,
                    urn,
                    "oracle_rules",
                    f"{len(rules)} oracle rule(s) declared but no 'projections' (the rules have no parameters: they would be inert).",
                )
            )
        if projections and not (e.get("governed_by_clauses") or []):
            findings.append(
                CatalogFinding(
                    "projections_without_clauses",
                    SEVERITY_WARNING,
                    urn,
                    "governed_by_clauses",
                    "projections declared but no 'governed_by_clauses' justifying them.",
                )
            )
    return findings


def check_intention_purity(entities: dict[str, Any]) -> list[CatalogFinding]:
    """Aucune valeur d'instanciation dans les projections ni dans le modèle de graphe de réconciliation."""
    findings: list[CatalogFinding] = []
    for urn, e in sorted(entities.items()):
        scopes: list[tuple[str, Any]] = [("projections", e.get("projections"))]
        template = e.get("hydration_template") or {}
        if isinstance(template, dict) and "reconciliation_graph" in template:
            scopes.append(("hydration_template.reconciliation_graph", template["reconciliation_graph"]))
        for scope_path, scope_value in scopes:
            if scope_value is None:
                continue
            for path, kind, literal in _instantiation_values(scope_value, scope_path):
                findings.append(
                    CatalogFinding(
                        "instantiation_value_in_intention",
                        SEVERITY_ERROR,
                        urn,
                        path,
                        f"{kind} value '{literal}' is an instantiation value: it belongs to the project's data, not to the shared ontology.",
                    )
                )
    return findings


def check_triplet_ids(triplets: list[dict[str, Any]]) -> list[CatalogFinding]:
    """Un identifiant de triplet doit être unique (avertissement : des consommateurs citent ces identifiants)."""
    seen: dict[str, int] = {}
    for t in triplets:
        seen[str(t.get("id"))] = seen.get(str(t.get("id")), 0) + 1
    return [
        CatalogFinding("duplicate_triplet_id", SEVERITY_WARNING, tid, "triplets",
                       f"triplet identifier '{tid}' is used {n} times: it no longer identifies one triplet.")
        for tid, n in sorted(seen.items()) if n > 1
    ]


def check_catalog(catalog: dict[str, Any]) -> list[CatalogFinding]:
    """Tous les contrôles ; la liste est triée de façon déterministe."""
    entities = catalog.get("entities") or {}
    findings = [*check_leaf_coherence(entities), *check_intention_purity(entities),
                *check_triplet_ids(catalog.get("triplets") or [])]
    return sorted(findings, key=lambda f: (f.severity != SEVERITY_ERROR, f.urn, f.code, f.path))


def has_errors(findings: list[CatalogFinding]) -> bool:
    return any(f.severity == SEVERITY_ERROR for f in findings)
