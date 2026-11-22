"""Contrôles de cohérence du catalogue d'ontologie servi (issues #190 et #191).

Quatre familles, appliquées à la forme « catalogue » (``entities``) :

1. **Cohérence interne d'une feuille** : une feuille qui déclare des ``oracle_rules`` doit fournir les ``projections``
   (paramètres des règles) ; des ``projections`` doivent être justifiées par des ``governed_by_clauses``.
2. **Pureté d'intention** : l'ontologie est une doctrine d'entreprise partagée par tous les projets ; elle ne porte pas de
   valeur d'INSTANCIATION (adresse IPv4/IPv6, CIDR, adresse MAC, numéro de VLAN). Contrôlé dans les ``projections`` et dans
   TOUT le ``hydration_template`` : un gabarit décrit une structure, pas des valeurs d'instance.
3. **Fiches de règles** : chaque règle nommée dans ``oracle_rules`` a une fiche dans ``rule_cards`` (objet vérifié,
   violation, paramètres, preuve, clauses). Une règle nommée sans fiche est une promesse sans définition.
4. **Énumérations** : une clé portant le nom d'une énumération du catalogue (``enumerations``) ne prend que ses valeurs.

Les instances concrètes (identifiants, tenants, sous-réseaux, VLAN) sont une donnée du PROJET, jamais de l'ontologie.
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

# Clés dont la valeur est par nature une instance (un numéro de VLAN identifie un VLAN d'un projet, pas une intention).
_INSTANCE_KEYS = frozenset({"vlan_id"})

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
            if k in _INSTANCE_KEYS and isinstance(v, (str, int)) and not isinstance(v, bool):
                found.append((f"{path}.{k}", "instance key", str(v)))
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
    """Aucune valeur d'instanciation dans les projections ni dans le gabarit d'hydratation."""
    findings: list[CatalogFinding] = []
    for urn, e in sorted(entities.items()):
        scopes: list[tuple[str, Any]] = [("projections", e.get("projections")), ("hydration_template", e.get("hydration_template"))]
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


def _rules_by_leaf(entities: dict[str, Any]) -> dict[str, list[str]]:
    """Règle d'oracle -> feuilles qui la nomment."""
    used: dict[str, list[str]] = {}
    for urn, e in sorted(entities.items()):
        if e.get("kind") != "leaf":
            continue
        for rule in e.get("oracle_rules") or []:
            used.setdefault(rule, []).append(urn)
    return used


def check_rule_cards(catalog: dict[str, Any]) -> list[CatalogFinding]:
    """Une règle nommée a une fiche ; la fiche ne lit que des paramètres que ses feuilles portent."""
    entities = catalog.get("entities") or {}
    cards: dict[str, Any] = catalog.get("rule_cards") or {}
    findings: list[CatalogFinding] = []
    used = _rules_by_leaf(entities)
    for rule, leaves in sorted(used.items()):
        card = cards.get(rule)
        if card is None:
            findings.append(
                CatalogFinding(
                    "rule_without_card",
                    SEVERITY_WARNING,
                    leaves[0],
                    f"oracle_rules[{rule}]",
                    f"rule '{rule}' is named but has no entry in 'rule_cards': what it checks, on which object, with which parameters and "
                    "which evidence is undefined.",
                )
            )
            continue
        for leaf in leaves:
            projections = (entities[leaf].get("projections") or {})
            for param in card.get("parameters") or []:
                if param not in projections:
                    findings.append(
                        CatalogFinding(
                            "rule_card_unknown_parameter",
                            SEVERITY_ERROR,
                            leaf,
                            f"rule_cards[{rule}].parameters",
                            f"the card of '{rule}' reads parameter '{param}', which this leaf does not carry in 'projections'.",
                        )
                    )
        leaf_clauses = {c for leaf in leaves for c in (entities[leaf].get("governed_by_clauses") or [])}
        for clause in card.get("clauses") or []:
            if clause not in leaf_clauses:
                findings.append(
                    CatalogFinding(
                        "rule_card_clause_not_on_leaf",
                        SEVERITY_WARNING,
                        leaves[0],
                        f"rule_cards[{rule}].clauses",
                        f"the card of '{rule}' cites clause '{clause}', which none of its leaves lists in 'governed_by_clauses'.",
                    )
                )
    for rule in sorted(set(cards) - set(used)):
        findings.append(
            CatalogFinding(
                "rule_card_orphan", SEVERITY_WARNING, rule, f"rule_cards[{rule}]", f"card for '{rule}', which no leaf names in 'oracle_rules'."
            )
        )
    return findings


def check_enumerations(catalog: dict[str, Any]) -> list[CatalogFinding]:
    """Une clé qui porte le nom d'une énumération ne prend que ses valeurs (``isolation_level`` : shared ... air-gap-physical)."""
    enums: dict[str, Any] = catalog.get("enumerations") or {}
    findings: list[CatalogFinding] = []
    allowed: dict[str, list[str]] = {}
    for name, enum in sorted(enums.items()):
        values = [v.get("value") for v in (enum.get("values") or [])]
        allowed[name] = values
        if len(values) != len(set(values)):
            findings.append(
                CatalogFinding("enumeration_duplicate_value", SEVERITY_ERROR, name, f"enumerations[{name}]", "the enumeration lists a value twice.")
            )

    def walk(value: Any, path: str, urn: str) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if k in allowed and isinstance(v, str) and v not in allowed[k]:
                    findings.append(
                        CatalogFinding(
                            "value_outside_enumeration",
                            SEVERITY_ERROR,
                            urn,
                            f"{path}.{k}",
                            f"'{v}' is not a value of enumeration '{k}' (allowed, from weakest to strongest: {', '.join(allowed[k])}).",
                        )
                    )
                walk(v, f"{path}.{k}", urn)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]", urn)

    for urn, e in sorted((catalog.get("entities") or {}).items()):
        for scope in ("projections", "hydration_template"):
            walk(e.get(scope), scope, urn)
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
    findings = [*check_leaf_coherence(entities), *check_intention_purity(entities), *check_rule_cards(catalog),
                *check_enumerations(catalog), *check_triplet_ids(catalog.get("triplets") or [])]
    return sorted(findings, key=lambda f: (f.severity != SEVERITY_ERROR, f.urn, f.code, f.path))


def has_errors(findings: list[CatalogFinding]) -> bool:
    return any(f.severity == SEVERITY_ERROR for f in findings)
