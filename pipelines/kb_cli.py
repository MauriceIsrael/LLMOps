"""``kb`` — knowledge base maintenance CLI (offline, run by maintainers).

Candidate cycle (plan L2):

    kb list [--status in_review]        list the candidate queue
    kb promote <candidate_id>           write an accepted candidate into data/kb (status: active)
    kb publish                          re-ingest, seal a snapshot, changelog, notify consumers
    kb remind                           re-notify owners of candidates waiting > 5 business days
    kb submit <file.jsonl>              submit candidate payloads (one JSON object per line)

Framework ingestion (plan L3):

    kb ingest-framework --framework NIS2 --version 2022/2555 --source <pdf|html|txt|docx>
    kb suggest-links --framework NIS2   (optional, offline LLM: LLM_ENDPOINT / LLM_MODEL)
    kb review-sheet --framework NIS2    (CSV + Markdown for the expert)
    kb apply-review <review_sheet.csv>  (candidates reviewed by the expert, promoted)
    kb declare-coverage --framework NIS2 --by @expert
    kb coverage NIS2 ISO27001 ...

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


@app.command("submit")
def submit_cmd(
    payloads: Path = typer.Argument(..., help="JSONL file: one candidate payload per line."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
) -> None:
    """Submit candidate payloads to the queue (automatic checks run immediately)."""
    service = _service(kb_dir, db_path)
    for n, line in enumerate(payloads.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            c = service.submit(json.loads(line), actor="kb submit")
        except (CandidateError, ValueError) as exc:
            console.print(f"[red]line {n}: {exc}[/red]")
            continue
        flags = [ch["name"] for ch in c["checks"] if ch["status"] != "pass"]
        console.print(f"{c['id']}  {c['status']:<13} {c['title']}  [dim]{', '.join(flags)}[/dim]")


STAGING_OPTION = typer.Option(Path("data/staging"), "--staging-dir", help="Staging directory (ignored by git).")


@app.command("ingest-framework")
def ingest_framework_cmd(
    framework: str = typer.Option(..., "--framework", help="Framework code (e.g. NIS2)."),
    version: str = typer.Option(..., "--version", help="Version of the source (e.g. 2022/2555)."),
    source: Path = typer.Option(..., "--source", help="Source document: pdf, html, txt, md, docx or doc."),
    tag: str = typer.Option("", "--tag", help="Document tag used by some splitters (e.g. TS22179)."),
    splitter: Path = typer.Option(None, "--splitter", help="Splitter configuration (default: splitters/<fw>.yaml)."),
    kb_dir: Path = KB_DIR_OPTION,
    staging_dir: Path = STAGING_OPTION,
) -> None:
    """Split a regulatory source into draft controls (staging) and update the framework manifest."""
    from pipelines.frameworks.ingest import ingest_framework

    try:
        res = ingest_framework(framework, version, source, kb_dir=kb_dir, staging_dir=staging_dir,
                               splitter=splitter, tag=tag)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        _fail(str(exc))
    console.print(f"[bold green]✓ {res['requirements']} draft control(s)[/bold green] in {res['staging_dir']}; "
                  f"manifest {res['manifest']} (source sha256 {res['source_sha256'][:12]}…).")
    if res["declaration_reset"]:
        console.print("[yellow]The previous coverage declaration was reset (new version or source).[/yellow]")


@app.command("suggest-links")
def suggest_links_cmd(
    framework: str = typer.Option(..., "--framework"),
    kb_dir: Path = KB_DIR_OPTION,
    staging_dir: Path = STAGING_OPTION,
) -> None:
    """Offline LLM proposals of links and acceptance criteria (llm-derived); skipped without LLM_ENDPOINT."""
    from pipelines.frameworks.ingest import latest_staging
    from pipelines.frameworks.links import suggest_links

    load_dotenv()
    res = suggest_links(latest_staging(staging_dir, framework), kb_dir)
    if res["skipped"]:
        console.print(f"[yellow]{res['reason']}[/yellow]")
    else:
        console.print(f"[bold green]✓ {res['updated']} draft(s) annotated[/bold green] by {res['model']} "
                      "(links_production_mode: llm-derived — to be reviewed).")


@app.command("review-sheet")
def review_sheet_cmd(
    framework: str = typer.Option(..., "--framework"),
    kb_dir: Path = KB_DIR_OPTION,
    staging_dir: Path = STAGING_OPTION,
) -> None:
    """Write the expert review sheet (CSV to fill in + Markdown view)."""
    from pipelines.frameworks.ingest import latest_staging
    from pipelines.frameworks.review import write_review_sheet

    res = write_review_sheet(latest_staging(staging_dir, framework), kb_dir)
    console.print(f"[bold green]✓ {res['rows']} row(s)[/bold green]: {res['csv']} (and {res['markdown']}).")


@app.command("apply-review")
def apply_review_cmd(
    sheet: Path = typer.Argument(..., help="Filled review_sheet.csv."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
) -> None:
    """Create the reviewed framework_ingestion candidates and promote the accepted ones."""
    from pipelines.frameworks.review import apply_review

    res = apply_review(sheet, _service(kb_dir, db_path))
    console.print(f"promoted: {len(res['promoted'])}, rejected: {len(res['rejected'])}, "
                  f"skipped (no decision): {len(res['skipped'])}, failed: {len(res['failed'])}")
    for f in res["failed"]:
        console.print(f"[red]  {f['requirement']}: {f['reason']}[/red]")
    if res["failed"]:
        raise typer.Exit(code=1)


@app.command("declare-coverage")
def declare_coverage_cmd(
    framework: str = typer.Option(..., "--framework"),
    by: str = typer.Option(..., "--by", help="Owner handle of the expert (data/kb/owners.yaml)."),
    kb_dir: Path = KB_DIR_OPTION,
) -> None:
    """Declare a framework covered; refused unless every expected requirement is active and validated."""
    from pipelines.frameworks.coverage import CoverageDeclarationError, declare_coverage

    try:
        cov = declare_coverage(framework, by, kb_dir)
    except CoverageDeclarationError as exc:
        _fail(str(exc))
    console.print(f"[bold green]✓ {framework} declared covered[/bold green] by {by} ({cov['expected']} requirements).")


@app.command("coverage")
def coverage_cmd(
    frameworks: list[str] = typer.Argument(..., help="Framework codes."),
    kb_dir: Path = KB_DIR_OPTION,
) -> None:
    """Print the coverage of frameworks by the knowledge base."""
    from pipelines.compliance_mapper import compute_framework_coverage

    console.print_json(json.dumps(compute_framework_coverage(frameworks, kb_dir), ensure_ascii=False))


@app.command("coverage-report")
def coverage_report_cmd(
    output: Path = typer.Option(Path("docs/COVERAGE.md"), "--output", help="Markdown report path."),
    kb_dir: Path = KB_DIR_OPTION,
) -> None:
    """Write the regulatory coverage report (docs/COVERAGE.md)."""
    from pipelines.frameworks.coverage import render_coverage_report

    output.write_text(render_coverage_report(kb_dir), encoding="utf-8")
    console.print(f"[bold green]✓ coverage report[/bold green] → {output}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
