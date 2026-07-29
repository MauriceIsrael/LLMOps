"""Tests unitaires isolés pour l'interface du Renderer et les outils FastMCP associés."""

from mcp_server.renderer_interface import RendererClient
from mcp_server.tools.renderer_tools import get_diagram_graph, get_render_payload, get_subject_trajectory_tool
from tools.elicitation.repository import ElicitationRepository


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

    payload = get_render_payload("demo", db_path=db_p)
    assert payload["engagement"] == "demo"
    assert "status" in payload

    diagram = get_diagram_graph("demo", db_path=db_p)
    assert "mermaid" in diagram

    trajectory = get_subject_trajectory_tool("demo", "mcx-services", db_path=db_p)
    assert isinstance(trajectory, list)
