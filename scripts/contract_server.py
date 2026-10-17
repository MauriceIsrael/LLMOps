"""Seeded LLMOps server for client contract tests (e.g. Archinex against the real contract).

Starts the real server on a scratch copy of the knowledge base with a SQLite governance
database, a delegating service token and a few test experts, so that a client can be exercised
end to end without touching the repository or any deployment.

    poetry run python scripts/contract_server.py [--port 8099]

Service token (header ``Authorization: Bearer contract-service-token``) carries ``kb:review`` and
``kb:delegate``; ``demo-token`` is the public demo token (no governance scope). Two more tokens serve the engagement
channel (contract 1.17+): ``arx-token`` (``eng:delegate``: acts for a member, named by ``X-Actor-Email``, as Archinex does) and
``suite-token`` (``eng:service``: reads a sealed engagement snapshot, as the suite does). Experts, acting
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

    # The scratch KB lives at ./data/kb: parts of the engine (RFP shredder, compliance mapper) read the relative
    # path data/kb from the working directory, which is the scratch directory.
    (tmp / "data").mkdir()
    kb = tmp / "data" / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    registry = yaml.safe_load((kb / "owners.yaml").read_text(encoding="utf-8"))
    for handle, (email, roles) in PERSONAS.items():
        entry = registry["owners"].get(handle) or {}
        entry.update(email=email, **({"roles": roles} if roles else {}))
        registry["owners"][handle] = entry
    (kb / "owners.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
    adr1 = kb / "decisions" / "ADR-0001.md"
    if adr1.exists():
        text = adr1.read_text(encoding="utf-8")
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            fm["revision"] = int(fm.get("revision", 1)) + 1  # an amended element is a new revision (K3 ledger)
            fm["assumptions"] = [
                "The control plane handles fewer than 10000 managed devices.",
                "Every site keeps an out-of-band access path to its routers."
            ]
            body = parts[2]
            body = body.replace(
                "The engagement needs backup, restore,",
                "The engagement needs backup, restore and restoration of network configuration after an outage, automated deployment,",
                1
            )
            adr1.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n" + body, encoding="utf-8")
    sim_yaml = kb / "taxonomy" / "similarity.yaml"
    if sim_yaml.exists():
        sim_cfg = yaml.safe_load(sim_yaml.read_text(encoding="utf-8")) or {}
        sim_cfg["thresholds"] = {"strong": 0.70, "possible": 0.30}
        sim_yaml.write_text(yaml.safe_dump(sim_cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    db = tmp / "knowledge.lbug"
    shutil.copy(ROOT / "data" / "knowledge.lbug", db)
    # An engagement snapshot resolves what its decisions and facts cite in the sealed knowledge snapshot: give the server the
    # repository's, so that a client can export an engagement end to end.
    (tmp / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    for snapshot in (ROOT / "data" / "snapshots").glob("*.json"):
        shutil.copy(snapshot, tmp / "data" / "snapshots" / snapshot.name)
    # The demonstration engagement, for the clients whose tests read it (get_board on nordwave-mcx-2027).
    (tmp / "data" / "engagements").mkdir(parents=True, exist_ok=True)
    for engagement in (ROOT / "data" / "engagements").glob("nordwave-mcx-2027.lbug"):
        shutil.copy(engagement, tmp / "data" / "engagements" / engagement.name)
    return {
        "LLMOPS_KB_DIR": str(kb),
        "LLMOPS_KNOWLEDGE_DB_PATH": str(db),
        "CANDIDATES_BACKEND": "sql",
        "GOVERNANCE_DATABASE_URL": f"sqlite:///{tmp / 'governance.db'}",
        "SERVER_TOKEN": "demo-token",
        "ENGAGEMENT_TOKENS": f"{SERVICE_TOKEN}:kb:review,kb:delegate,*;arx-token:*,eng:delegate;suite-token:*,eng:service",
        "LLMOPS_STORAGE_PERSISTENT": "true",
        "PYTHONPATH": str(ROOT),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 inside a container")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    tmp = Path(tempfile.mkdtemp(prefix="llmops-contract-"))
    try:
        env = prepare(tmp)
        os.environ.update(env)
        sys.path.insert(0, str(ROOT))
        eval_dataset = ROOT / "tests" / "evals" / "datasets" / "check_option_v1.jsonl"
        similarity_dataset = ROOT / "tests" / "evals" / "datasets" / "similarity_v1.jsonl"
        os.chdir(tmp)  # snapshots are written under ./data/snapshots
        import uvicorn

        from mcp_server.main import create_starlette_app
        from pipelines.governance.bootstrap import ensure_governance_ready

        ensure_governance_ready(tmp / "data" / "kb", eval_dataset, similarity_dataset)
        print(f"contract server on http://{args.host}:{args.port} (service token: {SERVICE_TOKEN})", flush=True)
        uvicorn.run(create_starlette_app(), host=args.host, port=args.port, log_level="warning")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
