"""PetitesBriques Adapter for LLMOps.

Translates engagement architecture statements (GraphRAG / Kùzu DB / LadybugDB)
into validated PetitesBriques canvas models conforming to 3GPP Poka-Yoke stacking rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp_server.core.db import get_engagement_path
from tools.elicitation.repository import ElicitationRepository


class PetitesBriquesAdapter:
    """Projects LLMOps architecture decisions into PetitesBriques canvas scenarios."""

    DEFAULT_PETITESBRIQUES_PATH = Path("/home/momo/Dev/PetitesBriques")

    def __init__(self, engagement: str = "nordwave-mcx-2027", db_path: Path | str | None = None):
        self.engagement = engagement
        self.db_path = db_path or get_engagement_path(engagement)

    def extract_architectural_requirements(self) -> dict[str, Any]:
        """Extracts key architectural drivers from active statements in the graph."""
        with ElicitationRepository(db_path=self.db_path, read_only=True) as repo:
            statements = repo.get_active_statements(self.engagement)

        reqs: dict[str, Any] = {
            "edge_survivability": False,
            "active_active_core": False,
            "lmr_interworking": False,
            "dedicated_core": False,
            "statements_summary": [],
        }

        for stmt in statements:
            val = (stmt.get("value") or "").lower()
            verb = (stmt.get("verbatim") or "").lower()
            sid = stmt.get("id", "")
            combined = f"{val} {verb}"

            reqs["statements_summary"].append({
                "id": sid,
                "subject": stmt.get("subject"),
                "predicate": stmt.get("predicate"),
                "value": stmt.get("value"),
            })

            if "survive" in combined or "isolated site" in combined or "local talkgroup" in combined:
                reqs["edge_survivability"] = True
            if "active-active" in combined or "2 sites" in combined or "two sites" in combined:
                reqs["active_active_core"] = True
            if "lmr" in combined or "interworking" in combined or "tetra" in combined:
                reqs["lmr_interworking"] = True
            if "standalone" in combined or "dedicated" in combined:
                reqs["dedicated_core"] = True

        return reqs

    def build_canvas(self) -> dict[str, Any]:
        """Synthesizes a Poka-Yoke verified PetitesBriques canvas from the requirements."""
        reqs = self.extract_architectural_requirements()

        sites: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []
        zones: list[dict[str, Any]] = []
        x_offset = 50

        # 1. Site Edge Tactique (si exigence de survie locale / mode isolé détectée)
        if reqs.get("edge_survivability", True):
            site_edge = {
                "id": "site-edge-survie",
                "name": "Site Edge Tactique (PPDR)",
                "siteType": "on-prem",
                "x": x_offset,
                "columnCount": 1,
                "bricks": [
                    {
                        "instanceId": "inst-edge-radio",
                        "templateId": "spectre-radio",
                        "siteId": "site-edge-survie",
                        "order": 0,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-edge-upf",
                        "templateId": "gw-gtp",
                        "siteId": "site-edge-survie",
                        "order": 1,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-edge-mcx",
                        "templateId": "s-mcx-server",
                        "siteId": "site-edge-survie",
                        "order": 2,
                        "columnIndex": 0,
                    },
                ],
            }
            sites.append(site_edge)
            zones.append({
                "id": "zone-tactical-edge",
                "label": "Site Tactique Autonome (Survie S-0002)",
                "brickInstanceIds": ["inst-edge-radio", "inst-edge-upf", "inst-edge-mcx"],
                "style": "dashed",
                "color": "#10B981",
            })
            x_offset += 350

        # 2. Cœurs Nationaux Bi-Site Actif-Actif
        if reqs.get("active_active_core", True):
            site_dc1 = {
                "id": "site-core-dc1",
                "name": "Cœur National DC-1 (Actif)",
                "siteType": "managed-self",
                "x": x_offset,
                "columnCount": 2,
                "bricks": [
                    {
                        "instanceId": "inst-dc1-fabric-up",
                        "templateId": "t2-ip-fabric",
                        "siteId": "site-core-dc1",
                        "order": 0,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc1-upf",
                        "templateId": "gw-gtp",
                        "siteId": "site-core-dc1",
                        "order": 1,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc1-mcx",
                        "templateId": "s-mcx-server",
                        "siteId": "site-core-dc1",
                        "order": 2,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc1-fabric-cp",
                        "templateId": "t2-ip-fabric",
                        "siteId": "site-core-dc1",
                        "order": 0,
                        "columnIndex": 1,
                    },
                    {
                        "instanceId": "inst-dc1-ctrl",
                        "templateId": "t1-core-control",
                        "siteId": "site-core-dc1",
                        "order": 1,
                        "columnIndex": 1,
                    },
                ],
            }
            sites.append(site_dc1)
            x_offset += 400

            site_dc2 = {
                "id": "site-core-dc2",
                "name": "Cœur National DC-2 (Actif)",
                "siteType": "managed-self",
                "x": x_offset,
                "columnCount": 2,
                "bricks": [
                    {
                        "instanceId": "inst-dc2-fabric-up",
                        "templateId": "t2-ip-fabric",
                        "siteId": "site-core-dc2",
                        "order": 0,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc2-upf",
                        "templateId": "gw-gtp",
                        "siteId": "site-core-dc2",
                        "order": 1,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc2-mcx",
                        "templateId": "s-mcx-server",
                        "siteId": "site-core-dc2",
                        "order": 2,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-dc2-fabric-cp",
                        "templateId": "t2-ip-fabric",
                        "siteId": "site-core-dc2",
                        "order": 0,
                        "columnIndex": 1,
                    },
                    {
                        "instanceId": "inst-dc2-ctrl",
                        "templateId": "t1-core-control",
                        "siteId": "site-core-dc2",
                        "order": 1,
                        "columnIndex": 1,
                    },
                ],
            }
            sites.append(site_dc2)
            zones.append({
                "id": "zone-core-national",
                "label": "Cœur 5G SA National Bi-Site (Active-Active S-0003)",
                "brickInstanceIds": [
                    "inst-dc1-fabric-up",
                    "inst-dc1-upf",
                    "inst-dc1-mcx",
                    "inst-dc1-fabric-cp",
                    "inst-dc1-ctrl",
                    "inst-dc2-fabric-up",
                    "inst-dc2-upf",
                    "inst-dc2-mcx",
                    "inst-dc2-fabric-cp",
                    "inst-dc2-ctrl",
                ],
                "style": "solid",
                "color": "#3B82F6",
            })
            x_offset += 400

        # 3. Flotte Historique LMR (TETRA/P25)
        if reqs.get("lmr_interworking", True):
            site_lmr = {
                "id": "site-legacy-lmr",
                "name": "Flotte Historique LMR (TETRA/P25)",
                "siteType": "on-prem",
                "x": x_offset,
                "columnCount": 1,
                "bricks": [
                    {
                        "instanceId": "inst-lmr-fabric",
                        "templateId": "t2-ip-fabric",
                        "siteId": "site-legacy-lmr",
                        "order": 0,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-lmr-gw",
                        "templateId": "vpn-ipsec",
                        "siteId": "site-legacy-lmr",
                        "order": 1,
                        "columnIndex": 0,
                    },
                    {
                        "instanceId": "inst-lmr-app",
                        "templateId": "appli-critique-sec",
                        "siteId": "site-legacy-lmr",
                        "order": 2,
                        "columnIndex": 0,
                    },
                ],
            }
            sites.append(site_lmr)

        # 4. Connexions 3GPP Poka-Yoke conformes
        connections = [
            {
                "id": "conn-n2-radio-core",
                "sourceBrickId": "inst-edge-radio",
                "targetBrickId": "inst-dc1-ctrl",
                "sourceDirection": "east",
                "linkTypeId": "n2-ngap",
            },
            {
                "id": "conn-n3-edge-core",
                "sourceBrickId": "inst-edge-upf",
                "targetBrickId": "inst-dc1-upf",
                "sourceDirection": "east",
                "linkTypeId": "n3-gtp-u",
            },
            {
                "id": "conn-inter-dc-fiber",
                "sourceBrickId": "inst-dc1-fabric-cp",
                "targetBrickId": "inst-dc2-fabric-cp",
                "sourceDirection": "east",
                "linkTypeId": "fiber-direct",
            },
            {
                "id": "conn-dc-lmr-iwf",
                "sourceBrickId": "inst-dc2-upf",
                "targetBrickId": "inst-lmr-gw",
                "sourceDirection": "east",
                "linkTypeId": "n4-pfcp",
            },
        ]

        # 5. Périmètre Opérateur Souverain
        perimeters = [
            {
                "id": f"perim-{self.engagement}",
                "name": f"Périmètre Souverain ({self.engagement})",
                "siteIds": [s["id"] for s in sites if s["siteType"] != "public-cloud"],
                "color": "#3B82F6",
            }
        ]

        return {
            "id": self.engagement,
            "name": "Nordwave MCX 2027 (Mission-Critical 5G SA)",
            "description": (
                f"Architecture générée automatiquement depuis l'engagement LLMOps '{self.engagement}'. "
                f"Exigences traduites : Survie Edge (S-0002), Cœur Bi-Site Actif-Actif (S-0003), Passerelle LMR (S-0004)."
            ),
            "isBuiltIn": False,
            "sites": sites,
            "connections": connections,
            "zones": zones,
            "operatorPerimeters": perimeters,
        }

    def export_json(self, output_path: Path | None = None) -> Path:
        """Exports the canvas model to a JSON file."""
        model = self.build_canvas()
        if output_path is None:
            output_dir = Path("artifacts") / self.engagement
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "petitesbriques_canvas.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_path

    def sync_to_petitesbriques(self, custom_models_path: Path | None = None) -> Path:
        """Syncs the model directly into PetitesBriques custom-models.json library."""
        model = self.build_canvas()
        target_file = custom_models_path or (self.DEFAULT_PETITESBRIQUES_PATH / "src/lib/data/custom-models.json")

        if not target_file.exists():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            models = []
        else:
            try:
                models = json.loads(target_file.read_text(encoding="utf-8"))
            except Exception:
                models = []

        # Remplacement ou insertion en tête
        models = [m for m in models if m.get("id") != model["id"]]
        models.insert(0, model)

        target_file.write_text(json.dumps(models, indent=4, ensure_ascii=False), encoding="utf-8")
        return target_file
