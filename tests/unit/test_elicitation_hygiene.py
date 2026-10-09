"""Élicitation: no debug output of answers, no silent default engagement or database (issues #81, #82)."""

import ast
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tools.elicitation.cli import app
from tools.elicitation.resolve import database_path, engagement_of, working_database

ROOT = Path(__file__).resolve().parents[2]
ELICITATION = ROOT / "tools" / "elicitation"


def test_no_print_in_the_flows():
    """A `print` in a flow writes the content of an expert's answer to the standard output (and to the container logs)."""
    offenders = []
    for path in sorted((ELICITATION / "flows").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_the_guard_sees_a_print(tmp_path):
    tree = ast.parse("def f():\n    print('x')\n")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print" for n in ast.walk(tree))


def test_no_default_engagement_or_database_in_the_engine():
    pattern = re.compile(r"demo-2026|data/kuzu_db")
    offenders = [f"{p.relative_to(ROOT)}:{i}" for p in sorted(ELICITATION.rglob("*.py"))
                 for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if pattern.search(line) and p.name != "resolve.py"]
    assert offenders == []


def test_the_engagement_is_never_guessed(monkeypatch):
    from mcp_server.core.config import DeploymentDefaultMissing

    monkeypatch.delenv("LLMOPS_ENGAGEMENT", raising=False)
    monkeypatch.setattr("mcp_server.core.config.server_config.engagement", None)
    with pytest.raises(DeploymentDefaultMissing):
        engagement_of(None)
    monkeypatch.setenv("LLMOPS_ENGAGEMENT", "from-env")
    assert engagement_of(None) == "from-env" and engagement_of("explicit") == "explicit"


def test_the_working_database_is_per_engagement_and_validated():
    assert database_path(None, "eng-a") == str(Path("artifacts") / "eng-a" / "graph")
    assert database_path(None, "eng-a") != database_path(None, "eng-b")  # two engagements never share a working graph
    assert database_path("/tmp/explicit", "eng-a") == "/tmp/explicit"
    with pytest.raises(Exception):  # noqa: B017 - an identifier that could leave the directory is refused
        working_database("../escape")


@pytest.mark.parametrize("command", ["conflicts", "subjects", "demote", "contest", "arbitrate", "import"])
def test_a_command_without_an_engagement_names_the_option_and_the_variable(monkeypatch, command):
    monkeypatch.delenv("LLMOPS_ENGAGEMENT", raising=False)
    monkeypatch.setattr("mcp_server.core.config.server_config.engagement", None)
    args = {"demote": ["x", "--to", "L1_framed", "--reason", "r"], "contest": ["S-1", "--text", "t"],
            "arbitrate": ["C-1", "--keep", "S-1", "--reason", "r"], "import": ["nofile.json"]}.get(command, [])
    result = CliRunner().invoke(app, [command, *args])
    assert result.exit_code != 0
    assert "--engagement" in result.output and "LLMOPS_ENGAGEMENT" in result.output
