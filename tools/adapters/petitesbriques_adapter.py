"""PetitesBriques Adapter for LLMOps.

Translates engagement architecture statements (GraphRAG / Kùzu DB / LadybugDB)
into validated PetitesBriques canvas models conforming to 3GPP Poka-Yoke stacking rules.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from mcp_server.core.db import get_engagement_path
from tools.elicitation.repository import ElicitationRepository


class PetitesBriquesAdapter:
    """Projects LLMOps architecture decisions into PetitesBriques canvas scenarios.

    Generic: the canvas (sites, bricks, zones, connections) and the requirement cues that
    select its blocks come from the engagement's canvas template,
    ``examples/<engagement>/petitesbriques_canvas.yaml`` by default.
    """

    DEFAULT_PETITESBRIQUES_PATH = Path("/home/momo/Dev/PetitesBriques")
    TEMPLATE_FILE = "petitesbriques_canvas.yaml"

    def __init__(
        self,
        engagement: str | None = None,
        db_path: Path | str | None = None,
        template_path: Path | str | None = None,
    ):
        from mcp_server.core.config import require_engagement
        from tools.elicitation.profile import engagement_file

        self.engagement = require_engagement(engagement)
        self.db_path = db_path or get_engagement_path(self.engagement)
        path = Path(template_path) if template_path else engagement_file(self.engagement, self.TEMPLATE_FILE)
        if path is None or not path.is_file():
            raise FileNotFoundError(
                f"No PetitesBriques canvas template for '{self.engagement}' "
                f"(expected examples/{self.engagement}/{self.TEMPLATE_FILE})."
            )
        self.template: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def extract_architectural_requirements(self) -> dict[str, Any]:
        """Extracts key architectural drivers from active statements in the graph."""
        with ElicitationRepository(db_path=self.db_path, read_only=True) as repo:
            statements = repo.get_active_statements(self.engagement)

        cues: dict[str, list[str]] = self.template.get("requirements") or {}
        reqs: dict[str, Any] = {flag: False for flag in cues}
        reqs["statements_summary"] = []

        for stmt in statements:
            val = (stmt.get("value") or "").lower()
            verb = (stmt.get("verbatim") or "").lower()
            combined = f"{val} {verb}"

            reqs["statements_summary"].append({
                "id": stmt.get("id", ""),
                "subject": stmt.get("subject"),
                "predicate": stmt.get("predicate"),
                "value": stmt.get("value"),
            })
            for flag, words in cues.items():
                if any(str(w).lower() in combined for w in words):
                    reqs[flag] = True

        return reqs

    def build_canvas(self) -> dict[str, Any]:
        """Synthesizes a PetitesBriques canvas from the template blocks selected by the requirements."""
        reqs = self.extract_architectural_requirements()
        tpl = self.template

        sites: list[dict[str, Any]] = []
        zones: list[dict[str, Any]] = []
        x_offset = int(tpl.get("x_start", 50))
        for block in tpl.get("blocks") or []:
            if not reqs.get(block.get("when"), True):
                continue
            for site in block.get("sites") or []:
                placed = {k: v for k, v in copy.deepcopy(site).items() if k != "advance"}
                placed["x"] = x_offset
                sites.append(placed)
                x_offset += int(site.get("advance", 0))
            zones.extend(copy.deepcopy(block.get("zones") or []))

        perimeter = tpl.get("perimeter") or {}
        perimeters = [
            {
                "id": f"perim-{self.engagement}",
                "name": str(perimeter.get("name", "{engagement}")).format(engagement=self.engagement),
                "siteIds": [s["id"] for s in sites if s["siteType"] != "public-cloud"],
                "color": perimeter.get("color", "#3B82F6"),
            }
        ]

        return {
            "id": self.engagement,
            "name": str(tpl.get("name") or self.engagement),
            "description": str(tpl.get("description") or "").format(engagement=self.engagement),
            "isBuiltIn": False,
            "sites": sites,
            "connections": copy.deepcopy(tpl.get("connections") or []),
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
