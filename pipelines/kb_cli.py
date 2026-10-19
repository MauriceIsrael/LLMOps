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

Consistency of the compiled graph with the files (issue #85):

    kb check [--strict]                 does data/knowledge.lbug describe data/kb? (the judge reads the graph, not the files)

Local semantic search (issue #94):

    kb models fetch                     download the pinned embedding model into data/models/ (once)
    kb models status                    ready | absent | off, as the server sees it
    kb embeddings index                 (re)encode the active assets (also done by every publication)

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


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_DB = ROOT / "data" / "governance.db"


def apply_governance_defaults(environ: dict[str, str] | None = None) -> bool:
    """Point the CLI at ``data/governance.db`` when it exists, as ``scripts/serve_local.py`` does.

    An explicit ``GOVERNANCE_DATABASE_URL`` or ``CANDIDATES_BACKEND`` always wins. Returns whether a governance
    database is configured after the defaults are applied.
    """
    import os

    env = os.environ if environ is None else environ
    if not env.get("GOVERNANCE_DATABASE_URL", "").strip() and not env.get("CANDIDATES_BACKEND", "").strip() and GOVERNANCE_DB.exists():
        env["CANDIDATES_BACKEND"] = "sql"
        env["GOVERNANCE_DATABASE_URL"] = f"sqlite:///{GOVERNANCE_DB.as_posix()}"
    return bool(env.get("GOVERNANCE_DATABASE_URL", "").strip()) or env.get("CANDIDATES_BACKEND", "").strip().lower() == "sql"


@app.callback()
def _main() -> None:
    load_dotenv()
    apply_governance_defaults()


def _service(kb_dir: Path, db_path: Path) -> CandidateService:
    load_dotenv()
    if not apply_governance_defaults():
        console.print(
            f"[yellow]! No governance database found ({GOVERNANCE_DB.relative_to(ROOT).as_posix()} is absent and "
            "GOVERNANCE_DATABASE_URL is not set): using the file queue (data/candidates), which the LLMOps server "
            "does not read when it runs with CANDIDATES_BACKEND=sql. Start "
            "scripts/serve_local.py once (or set GOVERNANCE_DATABASE_URL) to create it.[/yellow]"
        )
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
                                                db_path=db_path, ledger_path=kb_dir / "version-ledger.json",
                                                record_revisions=True),
    )
    if not result["published"]:
        console.print(f"[yellow]{result['message']}[/yellow]")
        return
    from pipelines.similarity.index import index_after_publication

    index = index_after_publication(kb_dir)
    console.print(f"embedding index: {index['status']} ({index.get('model')}"
                  + (f", {index['encoded']} encoded, {index['unchanged']} unchanged, {index['removed']} removed"
                     if index["status"] == "indexed" else f": {index.get('reason')}") + ")")
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


@app.command("import-proposals")
def import_proposals_cmd(
    snapshot: Path = typer.Argument(..., help="Sealed snapshot of proposals published by a suite application (JSON)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run the checks without creating any candidate."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
) -> None:
    """Read a sealed snapshot of proposals into candidates (K7): refused whole if altered, reviewed by a person, idempotent."""
    from pipelines.kb_candidates.proposals import ProposalSnapshotError, import_snapshot

    try:
        envelope = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"cannot read {snapshot}: {exc}")
    try:
        res = import_snapshot(_service(kb_dir, db_path), envelope, actor="kb import-proposals", dry_run=dry_run)
    except ProposalSnapshotError as exc:
        for p in exc.problems:
            console.print(f"[red]{p.code} {p.path}: {p.message}[/red]")
        _fail("snapshot refused: nothing was imported.")
    snap = res["snapshot"]
    console.print(f"[bold]{snap['sourceSystem']} / {snap['snapshotId']}[/bold] ({snap['checksum'][:19]}…)")
    for item in res["imported"]:
        label = item.get("id") or "(dry run)"
        console.print(f"{label}  {item.get('status') or item.get('would_be_status'):<13} {item['candidate_ref']}")
    for item in res["skipped"]:
        console.print(f"[dim]{item['id']}  already read  {item['candidate_ref']}[/dim]")
    for item in res["refused"]:
        console.print(f"[red]{item['candidate_ref']}: {item['argument']}: {item['reason']}[/red]")


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
    proposals: Path = typer.Option(None, "--proposals",
                                   help="JSON file of proposals already made (body of POST …/link-proposals)."),
    kb_dir: Path = KB_DIR_OPTION,
    staging_dir: Path = STAGING_OPTION,
) -> None:
    """Offline LLM proposals of links and acceptance criteria (llm-derived); skipped without LLM_ENDPOINT."""
    from pipelines.frameworks.ingest import latest_staging
    from pipelines.frameworks.links import apply_proposals_file, suggest_links

    if proposals is not None:
        res = apply_proposals_file(latest_staging(staging_dir, framework), proposals, kb_dir)
        console.print(f"[bold green]✓ {res['updated']} draft(s) annotated[/bold green] from {proposals} ({res['model']}; "
                      f"links_production_mode: llm-derived — to be reviewed); unknown links dropped: "
                      f"{res['dropped_unknown_links']}, unknown requirements: {res['unknown_requirements'] or 'none'}.")
        return
    load_dotenv()
    res = suggest_links(latest_staging(staging_dir, framework), kb_dir)
    if res["skipped"]:
        console.print(f"[yellow]{res['reason']}[/yellow]")
    else:
        console.print(f"[bold green]✓ {res['updated']} draft(s) annotated[/bold green] by {res['model']} "
                      "(links_production_mode: llm-derived — to be reviewed).")


@app.command("extract-triggers")
def extract_triggers_cmd(
    asset: str | None = typer.Option(None, "--asset", help="Only this element (default: every active principle, pattern and decision)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Read and propose, submit nothing."),
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
) -> None:
    """Offline LLM proposals of trigger rules (K22) from the consequence sections; candidates only, never published."""
    from pipelines.trigger_extraction import extract_triggers

    load_dotenv()
    res = extract_triggers(kb_dir, _service(kb_dir, db_path), asset_id=asset, dry_run=dry_run)
    if res["skipped"]:
        console.print(f"[yellow]{res['reason']}[/yellow]")
        return
    console.print(f"[bold green]✓ {len(res['submitted'])} rule candidate(s)[/bold green] by {res['model']} (llm-derived), "
                  f"{len(res['key_candidates'])} vocabulary key candidate(s), {len(res['unchanged'])} already known, "
                  f"{len(res['dropped'])} dropped.")
    for d in res["dropped"]:
        console.print(f"[yellow]  dropped {d.get('asset')} § {d.get('section')}: {d['reason']}[/yellow]")


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


@app.command("migrate-governance")
def migrate_governance_cmd(
    kb_dir: Path = KB_DIR_OPTION,
    candidates_dir: Path = typer.Option(Path("data/candidates"), help="File queue to import."),
    force_owners: bool = typer.Option(False, "--force-owners", help="Replace the stored owners registry."),
) -> None:
    """Import the file queue and data/kb/owners.yaml into the governance database (idempotent)."""
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import database_url

    if not database_url():
        _fail("No governance database: set GOVERNANCE_DATABASE_URL (or CANDIDATES_BACKEND=sql).")
    res = migrate_governance(kb_dir, candidates_dir, force_owners)
    console.print(f"candidates imported: {res['candidates_imported']} (already present: {res['candidates_skipped']}); "
                  f"owners seeded: {res['owners_seeded']}; evaluation cases: {res.get('eval_cases')}")


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


@app.command("check")
def check_cmd(
    kb_dir: Path = KB_DIR_OPTION,
    db_path: Path = DB_PATH_OPTION,
    strict: bool = typer.Option(False, "--strict", help="Also fail when the graph carries no file fingerprint (built before #85)."),
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """Check that the compiled graph (what the option judge reads) describes the knowledge base files (issue #85).

    Exit 0: consistent (or, without --strict, unverifiable because the graph predates the fingerprint: said loudly).
    Exit 1: a file changed, was added or removed since the graph was built. Nothing is rebuilt here."""
    from mcp_server.core.db import ReadOnlyKuzuClient
    from pipelines.kb_consistency import check_compiled_base

    client = ReadOnlyKuzuClient(db_path=db_path)
    report = check_compiled_base(kb_dir, lambda q, p: client.execute_cypher(q, p))
    if as_json:
        console.print_json(json.dumps(report, ensure_ascii=False))
    else:
        colour = {"ok": "green", "stale": "red", "unverified": "yellow"}[report["status"]]
        console.print(f"[bold {colour}]{report['status'].upper()}[/bold {colour}]  {report['files']} files, "
                      f"{report['assets_in_base']} assets in {db_path}")
        for key, label in (("changed_since_build", "changed since the graph was built"),
                           ("not_in_base", "in the files, not in the graph"),
                           ("removed_from_files", "in the graph, no longer in the files"),
                           ("unverified", "without fingerprint")):
            if report[key]["count"]:
                shown = ", ".join(report[key]["ids"][:10]) + (" …" if report[key]["count"] > 10 else "")
                console.print(f"  {label}: {report[key]['count']} ({shown})")
        if report.get("reason"):
            console.print(f"[{'red' if report['status'] == 'stale' else 'yellow'}]{report['reason']}[/]")
    if report["status"] == "stale" or (strict and report["status"] == "unverified"):
        raise typer.Exit(code=1)


@app.command("check-freshness")
def check_freshness_cmd(
    kb_dir: Path = KB_DIR_OPTION,
    as_json: bool = typer.Option(False, "--json", help="JSON output."),
    days: int = typer.Option(180, "--days", help="Default review cycle in days."),
) -> None:
    """Check freshness of regulatory frameworks and doctrine, alerting on overdue reviews and drifts (Issue #131)."""
    from pipelines.governance.freshness import check_kb_freshness, render_freshness_report

    report = check_kb_freshness(kb_dir, default_review_cycle_days=days)
    if as_json:
        console.print_json(json.dumps(report, ensure_ascii=False))
        return
    console.print(render_freshness_report(report))


@app.command("freshness-report")
def freshness_report_cmd(
    output: Path = typer.Option(Path("docs/FRESHNESS.md"), "--output", help="Markdown report path."),
    kb_dir: Path = KB_DIR_OPTION,
    days: int = typer.Option(180, "--days", help="Default review cycle in days."),
) -> None:
    """Write the regulatory and doctrine freshness report (docs/FRESHNESS.md)."""
    from pipelines.governance.freshness import check_kb_freshness, render_freshness_report

    report = check_kb_freshness(kb_dir, default_review_cycle_days=days)
    output.write_text(render_freshness_report(report), encoding="utf-8")
    console.print(f"[bold green]✓ freshness report[/bold green] → {output}")



models_app = typer.Typer(help="Local embedding models (data/models/, git-ignored): fetch once, then offline.",
                         no_args_is_help=True)
app.add_typer(models_app, name="models")

MODELS_DIR_OPTION = typer.Option(None, "--models-dir", help="Models directory (default: KB_MODELS_DIR or data/models).")


@models_app.command("fetch")
def models_fetch_cmd(
    model: str = typer.Option(None, "--model", help="Model id (default: KB_EMBEDDING_MODEL or the reference model)."),
    models_dir: Path = MODELS_DIR_OPTION,
    force: bool = typer.Option(False, "--force", help="Download again even when the local copy is intact."),
    from_dir: Path = typer.Option(None, "--from-dir", help="Install files downloaded elsewhere (see 'kb models urls') "
                                  "instead of downloading them; each one is checked against its pinned SHA-256."),
) -> None:
    """Download the pinned files of the embedding model and check their SHA-256 (the only network access).

    Behind a proxy inspecting HTTPS: KB_MODELS_CA_BUNDLE=<proxy root certificate, PEM>, KB_MODELS_BASE_URL=<mirror>,
    or --from-dir. TLS verification is never disabled."""
    from pipelines.similarity.encoder import reset_cache, settings
    from pipelines.similarity.models import fetch, spec_for

    s = settings()
    try:
        spec = spec_for(model or s.model)
    except ValueError as exc:
        _fail(str(exc))
    if not spec.files:
        console.print(f"[yellow]{spec.id} has no file to fetch.[/yellow]")
        return
    try:
        path = fetch(spec, models_dir or s.models_dir, force=force, source_dir=from_dir)
    except Exception as exc:  # network, disk or integrity: nothing half-installed is ever loaded
        _fail(f"fetch failed: {exc}")
    reset_cache()
    console.print(f"[bold green]✓ {spec.id}[/bold green] @ {spec.version[:12]} in {path} "
                  f"(model sha256 {spec.sha256}). Restart the server, then 'kb embeddings index' or publish.")


@models_app.command("urls")
def models_urls_cmd(
    model: str = typer.Option(None, "--model", help="Model id (default: KB_EMBEDDING_MODEL or the reference model)."),
) -> None:
    """Files to download by hand for 'kb models fetch --from-dir' (name, URL, pinned SHA-256)."""
    from pipelines.similarity.encoder import settings
    from pipelines.similarity.models import file_urls, spec_for

    try:
        spec = spec_for(model or settings().model)
    except ValueError as exc:
        _fail(str(exc))
    hashes = {spec.local_name(r): h for r, h in spec.files.items()}
    for name, url in file_urls(spec).items():
        console.print(f"{name}\t{url}\tsha256 {hashes[name]}", soft_wrap=True, highlight=False)


@models_app.command("status")
def models_status_cmd() -> None:
    """Status of the reference embedding model as the server sees it (ready, absent or off)."""
    from pipelines.similarity.encoder import embedding_status

    console.print_json(json.dumps(embedding_status(), ensure_ascii=False))


embeddings_app = typer.Typer(help="Vectors of the knowledge base computed by the server's reference model.",
                             no_args_is_help=True)
app.add_typer(embeddings_app, name="embeddings")


@embeddings_app.command("index")
def embeddings_index_cmd(kb_dir: Path = KB_DIR_OPTION) -> None:
    """(Re)encode the active assets whose text changed and drop the vectors of retired ones (as a publication does)."""
    from pipelines.governance.store import database_url
    from pipelines.similarity.encoder import reference_encoder
    from pipelines.similarity.index import build_index
    from pipelines.similarity.store import EmbeddingStore

    load_dotenv()
    if not database_url():
        _fail("No governance database: set GOVERNANCE_DATABASE_URL (or CANDIDATES_BACKEND=sql).")
    encoder, status = reference_encoder()
    if encoder is None:
        _fail(f"embedding model {status['model']} is {status['status']}: {status.get('reason')}")
        return
    res = build_index(EmbeddingStore(), kb_dir, encoder)
    console.print_json(json.dumps(res, ensure_ascii=False))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
