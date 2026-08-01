"""Tests unitaires isolés pour l'interface du Renderer et les outils FastMCP associés."""

import pytest

from mcp_server.renderer_interface import RendererClient
from mcp_server.tools.renderer_tools import (
    get_diagram_graph,
    get_render_payload,
    get_subject_trajectory_tool,
)
from tools.elicitation.repository import ElicitationRepository

pytestmark = pytest.mark.deterministic


def test_renderer_client_payload(tmp_path):
    db_p = str(tmp_path / "test_kuzu")
    repo = ElicitationRepository(db_path=db_p)
    repo.save_subject("demo", "mcx-services", "L1_framed")
    repo.close()

    client = RendererClient(engagement="demo", db_path=db_p)
    payload = client.fetch_render_payload()

    assert payload.engagement == "demo"
    assert payload.status in ("provisional", "final")
    assert isinstance(payload.maturity_board, list)
    assert isinstance(payload.active_statements, list)


def test_renderer_client_diagram_graph(tmp_path):
    db_p = str(tmp_path / "test_kuzu")
    repo = ElicitationRepository(db_path=db_p)
    repo.save_subject("demo", "mcx-services", "L1_framed")
    repo.close()

    client = RendererClient(engagement="demo", db_path=db_p)
    diagram = client.fetch_diagram_graph(format="mermaid")

    assert diagram.engagement == "demo"
    assert "flowchart TD" in diagram.mermaid
    assert isinstance(diagram.nodes, list)
    assert isinstance(diagram.edges, list)


def test_renderer_tools_direct_call(tmp_path):
    db_p = str(tmp_path / "test_kuzu")
    repo = ElicitationRepository(db_path=db_p)
    repo.save_subject("demo", "mcx-services", "L1_framed")
    repo.close()

    res = get_render_payload("demo", db_path=db_p)
    assert res["status"] == "ok"
    payload = res["data"]
    assert payload["engagement"] == "demo"
    assert "status" in payload

    res_diag = get_diagram_graph("demo", db_path=db_p)
    assert res_diag["status"] == "ok"
    diagram = res_diag["data"]
    assert "mermaid" in diagram

    res_traj = get_subject_trajectory_tool("demo", "mcx-services", db_path=db_p)
    assert res_traj["status"] == "ok"
    assert isinstance(res_traj["data"], list)
