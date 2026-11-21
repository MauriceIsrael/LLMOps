"""Chargement du catalogue d'ontologie servi aux clients (``/api/knowledge/ontology/export``, outil MCP).

Une seule forme est servie : le **catalogue** (``catalog_version``, ``entities``, ``triplets``, ``clause_index``),
décrit par ``schemas/ontology_catalog.schema.json``.

Le producteur « entries » (``pipelines.ontology.export``) écrit une AUTRE forme (``payload.entries``) ; il écrit dans
``DEFAULT_EXPORT_PATH`` (un chemin distinct) et ne doit jamais remplacer le catalogue. Ce module ne régénère donc rien et
n'avale aucune exception : un fichier absent ou d'une autre forme est une erreur explicite, jamais une autre forme servie
silencieusement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CATALOG_PATH = Path("data/snapshots/ontology_export.json")


class OntologyCatalogUnavailableError(Exception):
    """Le catalogue ne peut pas être servi. ``code`` est stable (utilisable par les clients et les tests)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def load_catalog_document(path: str | Path | None = None) -> dict[str, Any]:
    """Charge et normalise le catalogue : enveloppe ``payload`` dépliée, ``clause_index`` garanti.

    Raises:
        OntologyCatalogUnavailableError: ``ontology_export_not_found`` (fichier absent) ou
            ``ontology_export_wrong_shape`` (pas de ``entities`` : par exemple la forme ``payload.entries``).
    """
    catalog_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    if not catalog_path.is_file():
        raise OntologyCatalogUnavailableError(
            "ontology_export_not_found",
            f"Ontology catalog not found at '{catalog_path}'. Run the catalog build; the entries exporter "
            f"(pipelines.ontology.export) does not produce this file.",
        )

    with open(catalog_path, encoding="utf-8") as f:
        data = json.load(f)

    payload = data.get("payload")
    if isinstance(payload, dict) and "entities" in payload:
        data = {
            "catalog_version": payload.get("schema_version") or data.get("schema_version", "1.0"),
            "generated_at": data.get("generated_at") or "2026-10-29T10:00:00Z",
            "entities": payload.get("entities", {}),
            "triplets": payload.get("triplets", []),
            "clause_index": payload.get("clause_index") or {},
        }

    if not isinstance(data.get("entities"), dict):
        raise OntologyCatalogUnavailableError(
            "ontology_export_wrong_shape",
            f"'{catalog_path}' is not an ontology catalog: field 'entities' is missing "
            f"(found keys: {sorted(data.keys())}). The 'payload.entries' shape is not served.",
        )

    if not data.get("clause_index"):
        from pipelines.ontology.catalog import build_clause_index

        data["clause_index"] = build_clause_index(data.get("entities", {}), data.get("triplets", []))
    return data
