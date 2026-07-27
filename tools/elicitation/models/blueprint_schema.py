"""Schéma Pydantic et chargeur pour les blueprints d'architecture structurés."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class BlueprintRequirement(BaseModel):
    """Exigence de maturité d'un sujet pour une section."""
    subject: str
    level: str = "L1_framed"


class BlueprintSection(BaseModel):
    """Section d'un blueprint décrivant une exigence documentaire."""
    id: str
    title: str
    must_answer: str
    requires: list[BlueprintRequirement] = Field(default_factory=list)
    requires_subjects: list[str] = Field(default_factory=list)
    unlocks: list[str] = Field(default_factory=list)
    min_level_final: str = "L3_decided"
    min_level_provisional: str = "L1_framed"
    informed_by: list[str] = Field(default_factory=list)
    routes_to: str

    def get_requirements(self) -> list[BlueprintRequirement]:
        """Retourne la liste des exigences de maturité pour cette section."""
        if self.requires:
            return self.requires
        reqs = []
        for s in self.requires_subjects:
            reqs.append(BlueprintRequirement(subject=s, level=self.min_level_provisional or "L1_framed"))
        return reqs


class BlueprintRoot(BaseModel):
    """Sujet racine initial d'un blueprint."""
    name: str
    definition: str = ""
    instructed: bool = True


class Blueprint(BaseModel):
    """Blueprint d'architecture globale."""
    id: str
    title: str
    type: str = "blueprint"
    status: str = "active"
    domain: list[str] = Field(default_factory=list)
    roots: list[BlueprintRoot] = Field(default_factory=list)
    sections: list[BlueprintSection] = Field(default_factory=list)

    def get_declared_subjects(self) -> set[str]:
        """Retourne l'ensemble des sujets de cadrage initial déclarés par le blueprint."""
        if self.roots:
            return {r.name for r in self.roots if r.instructed}
        subjects = set()
        for sec in self.sections:
            if sec.unlocks or sec.id in ("4.1", "5.1"):
                for req in sec.get_requirements():
                    if req.level == "L1_framed":
                        subjects.add(req.subject)
        return subjects


def load_blueprint(path: str | Path) -> Blueprint:
    """Charge un blueprint d'architecture depuis un fichier YAML ou Markdown avec frontmatter."""
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Blueprint introuvable : {filepath}")

    text = filepath.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            data = yaml.safe_load(parts[1])
            return Blueprint(**data)

    data = yaml.safe_load(text)
    return Blueprint(**data)
