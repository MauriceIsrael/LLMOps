"""Fichier d'Interface Python & Contrat d'Intégration pour le Moteur de Rendu (Renderer).

Ce module permet à tout moteur de rendu (Web, React, PDF, CLI, Graph) d'interagir
directement avec la plateforme LLMOps via des structures typées ou via le Serveur FastMCP.
"""

from dataclasses import dataclass, field
from typing import Any, Literal
from mcp_server.tools.renderer_tools import get_diagram_graph, get_render_payload, get_subject_trajectory_tool


@dataclass
class SubjectMaturity:
    subject: str
    name: str
    level: str  # L0_named | L1_framed | L2_decomposed | L3_decided | L4_specified
    origin: str  # blueprint | discovered
    updated_at: str
    is_stalled: bool = False
    days_at_level: int = 0
    open_question_ref: str | None = None
    assigned_role: str | None = None


@dataclass
class ArchitecturalStatement:
    id: str
    section: str
    subject: str
    predicate: str
    value: str
    author: str
    role: str
    confidence: str  # assumed | designed | committed | stated-by-client
    status: str  # active | under_review | superseded
    verbatim: str = ""


@dataclass
class ArchitecturalConflict:
    id: str
    kind: str  # contradiction | tension
    detail: str
    status: str  # open | arbitrated | resolved
    origin: str  # declared | detected
    statement_ids: list[str] = field(default_factory=list)
    resolution: str | None = None
    arbitrated_by: str | None = None


@dataclass
class TrajectoryStep:
    level: str
    question: str
    answer_excerpt: str


@dataclass
class RenderPayload:
    engagement: str
    status: Literal["provisional", "final"]
    is_provisional: bool
    maturity_board: list[dict[str, Any]]
    active_statements: list[dict[str, Any]]
    open_conflicts: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    unripe_subjects: list[str]


@dataclass
class DiagramGraph:
    engagement: str
    format: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    mermaid: str


class RendererClient:
    """Client Python d'interface avec le moteur d'architecture LLMOps."""

    def __init__(self, engagement: str = "nordwave-mcx-2027", db_path: str | None = None):
        self.engagement = engagement
        self.db_path = db_path

    def fetch_render_payload(self) -> RenderPayload:
        """Récupère l'intégralité du payload structuré pour le rendu de document."""
        raw_res = get_render_payload(engagement=self.engagement, db_path=self.db_path)
        raw = raw_res.get("data", raw_res)
        return RenderPayload(
            engagement=raw["engagement"],
            status=raw["status"],
            is_provisional=raw["is_provisional"],
            maturity_board=raw["maturity_board"],
            active_statements=raw["active_statements"],
            open_conflicts=raw["open_conflicts"],
            uncertainties=raw["uncertainties"],
            unripe_subjects=raw["unripe_subjects"],
        )

    def fetch_diagram_graph(self, format: str = "mermaid") -> DiagramGraph:
        """Récupère la structure de graphe ou le code Mermaid pour l'affichage de diagrammes."""
        raw_res = get_diagram_graph(engagement=self.engagement, format=format, db_path=self.db_path)
        raw = raw_res.get("data", raw_res)
        return DiagramGraph(
            engagement=raw["engagement"],
            format=raw["format"],
            nodes=raw["nodes"],
            edges=raw["edges"],
            mermaid=raw["mermaid"],
        )

    def fetch_subject_trajectory(self, subject: str) -> list[TrajectoryStep]:
        """Récupère la trajectoire d'avancement par niveau de maturité d'un sujet."""
        raw_res = get_subject_trajectory_tool(engagement=self.engagement, subject=subject, db_path=self.db_path)
        raw = raw_res.get("data", raw_res)
        return [
            TrajectoryStep(
                level=step["level"],
                question=step["question"],
                answer_excerpt=step["answer_excerpt"],
            )
            for step in raw
        ]
