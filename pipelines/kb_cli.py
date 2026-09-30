"""``kb`` — knowledge base maintenance CLI (offline, run by maintainers).

Candidate cycle (plan L2):

    kb list [--status in_review]        list the candidate queue
    kb promote <candidate_id>           write an accepted candidate into data/kb (status: active)
    kb publish                          re-ingest, seal a snapshot, changelog, notify consumers
    kb remind                           re-notify owners of candidates waiting > 5 business days

The commit of the knowledge base is left to the maintainer.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError
from pipelines.kb_candidates.service import CandidateService

app = typer.Typer(help="Knowledge base maintenance: candidate cycle, promotion and publication.", no_args_is_help=True)
console = Console()

KB_DIR_OPTION = typer.Option(Path("data/kb"), "--kb-dir", help="Knowledge base directory.")
DB_PATH_OPTION = typer.Option(Path("data/knowledge.lbug"), "--db-path", help="Knowledge graph database.")


def _doctrine_loader(db_path: Path, kb_dir: Path):
    def load():
        from mcp_server.core.db import ReadOnlyKuzuClient
        from pipelines.doctrine import load_index

        client = ReadOnlyKuzuClient(db_path=db_path)
        return load_index(lambda q, p: client.execute_cypher(q, p), kb_dir)

    return load


def _service(kb_dir: Path, db_path: Path) -> CandidateService:
    load_dotenv()
    return CandidateService(kb_dir=kb_dir, doctrine_index_loader=_doctrine_loader(db_path, kb_dir))


def _fail(message: str) -> None:
    console.print(f"[bold red]✗ {message}[/bold red]")
    raise typer.Exit(code=1)


@app.command("list")
def list_cmd(
    status: str = typer.Option(None, "--status", help="Filter by status."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """List KB candidates (newest first)."""
    items = _service(kb_dir, db_path).find(status=status)
    if as_json:
        console.print_json(json.dumps(items, ensure_ascii=False))
        return
    for c in items:
        flags = [ch["name"] for ch in c.get("checks") or [] if ch["status"] != "pass"]
        console.print(f"{c['id']}  {c['status']:<13} {c['kind']:<19} {c.get('assigned_owner') or '-':<28} "
                      f"{c['title']}  [dim]{', '.join(flags)}[/dim]")


@app.command("promote")
def promote_cmd(
    candidate_id: str = typer.Argument(..., help="Accepted candidate to write into the knowledge base."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
) -> None:
    """Write an accepted candidate into data/kb with status active and computed confidence."""
    from pipelines.kb_candidates.confidence import NotPublishableError

    try:
        c = _service(kb_dir, db_path).promote(candidate_id)
    except CandidateNotFoundError:
        _fail(f"unknown candidate {candidate_id}")
    except (CandidateError, NotPublishableError) as exc:
        _fail(str(exc))
    console.print(f"[bold green]✓ {candidate_id} promoted[/bold green] → {c['promoted']['path']} "
                  f"(confidence: {c['promoted']['confidence']}). Run 'kb publish', then commit data/kb.")


def rebuild_knowledge_db(kb_dir: Path, db_path: Path) -> None:
    """Re-ingest the knowledge base into a fresh graph database."""
    from pipelines.cli import ingest
    from tools.adapters.ladybug_store import LadybugGraphStore

    LadybugGraphStore.clear_cache(str(db_path))
    if db_path.is_dir():
        shutil.rmtree(db_path)
    elif db_path.exists():
        db_path.unlink()
    try:
        ingest(kb_dir=kb_dir, db_path=db_path)
    except SystemExit:
        pass
    LadybugGraphStore.clear_cache(str(db_path))


@app.command("publish")
def publish_cmd(
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
    snapshot_dir: Path = typer.Option(Path("data/snapshots"), "--snapshot-dir", help="Sealed snapshots directory."),
    fixture: Path = typer.Option(Path("fixtures/sealed_snapshot.json"), "--fixture", help="Sealed snapshot fixture."),
) -> None:
    """Publish promoted candidates: ingest, sealed snapshot, CHANGELOG, consumer notification."""
    import sys

    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:  # console scripts do not put the repository on sys.path
        sys.path.insert(0, repo_root)
    from scripts.export_sealed_snapshot import export_sealed_snapshot

    result = _service(kb_dir, db_path).publish(
        ingest=lambda: rebuild_knowledge_db(kb_dir, db_path),
        snapshot=lambda: export_sealed_snapshot(output_fixtures_path=fixture, output_snapshot_dir=snapshot_dir,
                                                db_path=db_path),
    )
    if not result["published"]:
        console.print(f"[yellow]{result['message']}[/yellow]")
        return
    console.print(f"[bold green]✓ published {', '.join(result['published'])}[/bold green] "
                  f"in {result['snapshot_id']} (notified: {', '.join(result['channels'])}). "
                  "Review and commit data/kb, data/knowledge.lbug and the snapshot.")


@app.command("remind")
def remind_cmd(kb_dir: Path = KB_DIR_OPTION, db_path: Path = DB_PATH_OPTION) -> None:
    """Re-notify owners of candidates in review for more than 5 business days (for cron)."""
    reminded = _service(kb_dir, db_path).remind()
    console.print(f"{len(reminded)} reminder(s) sent" + (": " + ", ".join(c["id"] for c in reminded) if reminded else ""))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
