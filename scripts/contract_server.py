"""Seeded LLMOps server for client contract tests (e.g. Archinex against the real contract).

Starts the real server on a scratch copy of the knowledge base with a SQLite governance
database, a delegating service token and a few test experts, so that a client can be exercised
end to end without touching the repository or any deployment.

    poetry run python scripts/contract_server.py [--port 8099]

Service token (header ``Authorization: Bearer contract-service-token``) carries ``kb:review`` and
``kb:delegate``; ``demo-token`` is the public demo token (no governance scope). Experts, acting
through ``X-Actor-Email``:

    alice@example.org  @core-owner-architecture  (owns architecture, automation, network-automation...)
    sec@example.org    @security-compliance-team (owns security-governance: NIS2 requirements)
    eva@example.org    @ciso-office              kb:evaluate
    maint@example.org  @maintainers              kb:maintain, kb:admin

Everything lives in a temporary directory removed on exit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICE_TOKEN = "contract-service-token"
PERSONAS = {
    "@core-owner-architecture": ("alice@example.org", []),
    "@security-compliance-team": ("sec@example.org", []),
    "@ciso-office": ("eva@example.org", ["kb:evaluate"]),
    "@maintainers": ("maint@example.org", ["kb:maintain", "kb:admin"]),
}


def prepare(tmp: Path) -> dict[str, str]:
    """Scratch copy of the knowledge base and graph, owners with e-mails, environment variables."""
    import yaml

    kb = tmp / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    registry = yaml.safe_load((kb / "owners.yaml").read_text(encoding="utf-8"))
    for handle, (email, roles) in PERSONAS.items():
        entry = registry["owners"].get(handle) or {}
        entry.update(email=email, **({"roles": roles} if roles else {}))
        registry["owners"][handle] = entry
    (kb / "owners.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
    db = tmp / "knowledge.lbug"
    shutil.copy(ROOT / "data" / "knowledge.lbug", db)
    (tmp / "data").mkdir()
    return {
        "LLMOPS_KB_DIR": str(kb),
        "LLMOPS_KNOWLEDGE_DB_PATH": str(db),
        "CANDIDATES_BACKEND": "sql",
        "GOVERNANCE_DATABASE_URL": f"sqlite:///{tmp / 'governance.db'}",
        "SERVER_TOKEN": "demo-token",
        "ENGAGEMENT_TOKENS": f"{SERVICE_TOKEN}:kb:review,kb:delegate,*",
        "LLMOPS_STORAGE_PERSISTENT": "true",
        "PYTHONPATH": str(ROOT),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    tmp = Path(tempfile.mkdtemp(prefix="llmops-contract-"))
    try:
        env = prepare(tmp)
        os.environ.update(env)
        sys.path.insert(0, str(ROOT))
        eval_dataset = ROOT / "tests" / "evals" / "datasets" / "check_option_v1.jsonl"
        os.chdir(tmp)  # snapshots are written under ./data/snapshots
        import uvicorn

        from mcp_server.main import create_starlette_app
        from pipelines.governance.bootstrap import ensure_governance_ready

        ensure_governance_ready(tmp / "kb", eval_dataset)
        print(f"contract server on http://127.0.0.1:{args.port} (service token: {SERVICE_TOKEN})", flush=True)
        uvicorn.run(create_starlette_app(), host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
