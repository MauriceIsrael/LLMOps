"""CLI Typer pour lancer le pipeline d'ingestion de la base de connaissances dans Kùzu DB."""

from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import track

from pipelines.ingestion.graph_loader import KuzuGraphLoader
from pipelines.ingestion.llama_extractor import ArchitectureGraphExtractor
from pipelines.ingestion.markdown_parser import MarkdownDocParser

app = typer.Typer(
    help="CLI d'ingestion des documents d'architecture Markdown vers le Graphe de Connaissances Kùzu DB."
)
console = Console()



@app.command(name="ingest")
def ingest(

    kb_dir: Path = typer.Option(
        Path("data/kb"),
        "--kb-dir",
        "-k",
        help="Répertoire racine de la base de connaissances d'architecture.",
    ),
    db_path: Path = typer.Option(
        Path("data/knowledge.lbug"),
        "--db-path",
        "-d",
        help="Chemin de stockage de la base LadybugDB.",
    ),
) -> None:
    """Ingère tous les fichiers Markdown du dossier KB et construit le graphe dans Kùzu DB."""
    load_dotenv()
    console.print(f"[bold blue]🚀 Démarrage de l'ingestion depuis :[/bold blue] {kb_dir}")


    if not kb_dir.exists():
        console.print(f"[bold red]❌ Le répertoire {kb_dir} n'existe pas.[/bold red]")
        raise typer.Exit(code=1)

    all_files = sorted(
        [
            p
            for p in list(kb_dir.rglob("*.md")) + list(kb_dir.rglob("*.yaml")) + list(kb_dir.rglob("*.yml"))
            if not p.name.startswith("_") and p.name not in ("README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "deltas.md")
        ]
    )
    console.print(f"[bold green]📄 {len(all_files)} fichiers d'architecture (Markdown & YAML) trouvés.[/bold green]")

    parser = MarkdownDocParser()
    extractor = ArchitectureGraphExtractor()
    loader = KuzuGraphLoader(db_path=db_path)

    total_nodes = 0
    total_rels = 0

    all_parsed_data: list[tuple[list[Any], list[Any]]] = []

    try:
        for file_path in track(all_files, description="Ingestion des nœuds..."):
            try:
                parsed_doc = parser.parse_file(file_path)
                if not parsed_doc:
                    continue
                nodes, rels = extractor.extract_nodes_and_relations(parsed_doc)
                loader.load_doc_nodes_and_rels(nodes, [])
                total_nodes += len(nodes)
                all_parsed_data.append((nodes, rels))
            except Exception as e:
                console.print(f"[bold yellow]⚠️ Erreur lors du traitement de {file_path.name} : {e}[/bold yellow]")

        for _, rels in track(all_parsed_data, description="Création des relations..."):
            if rels:
                try:
                    loader.load_doc_nodes_and_rels([], rels)
                    total_rels += len(rels)
                except Exception as e:
                    console.print(f"[bold yellow]⚠️ Erreur lors de la création des relations : {e}[/bold yellow]")
    finally:
        loader.store.close()
        from tools.adapters.ladybug_store import LadybugGraphStore
        LadybugGraphStore.clear_cache(loader.db_path)

    console.print(
        f"[bold green]✅ Ingestion terminée avec succès ![/bold green]\n"
        f"📊 [bold]{total_nodes}[/bold] nœuds et [bold]{total_rels}[/bold] relations enregistrés dans [bold]{db_path}[/bold]."
    )



@app.command(name="visualize")
def visualize_cmd(
    db_path: Path = typer.Option(
        Path("data/knowledge.lbug"),
        "--db-path",
        "-d",
        help="Chemin de stockage de la base LadybugDB.",
    ),
    output: Path = typer.Option(
        Path("docs/graph_explorer.html"),
        "--output",
        "-o",
        help="Chemin du fichier HTML de sortie.",
    ),
) -> None:
    """Génère un visualiseur Web HTML interactif (Vis.js) pour explorer le graphe Kùzu DB."""
    from pipelines.visualization.graph_visualizer import GraphVisualizer

    console.print(f"[bold blue]🎨 Génération du visualiseur de graphe depuis :[/bold blue] {db_path}")
    viz = GraphVisualizer(db_path=db_path)
    out_path = viz.generate_html(output_path=output)
    console.print(
        f"[bold green]✨ Visualiseur interactif généré avec succès ![/bold green]\n"
        f"👉 Ouvrez [bold]{out_path}[/bold] dans votre navigateur."
    )


@app.command(name="reconcile")
def reconcile_cmd(
    kb_dir: Path = typer.Option(
        Path("data/kb"),
        "--kb-dir",
        "-k",
        help="Répertoire racine de la base de connaissances.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simuler sans modifier les fichiers Markdown.",
    ),
) -> None:
    """Réconcilie sémantiquement les assets KB avec les contrôles réglementaires (NIS2, SecNumCloud, ISO 27001, 3GPP)."""
    from pipelines.compliance_mapper import reconcile_kb_assets

    console.print(f"[bold blue]🔗 Lancement de la réconciliation sémantique (dry_run={dry_run})...[/bold blue]")
    res = reconcile_kb_assets(kb_dir=kb_dir, dry_run=dry_run)
    count = res["updated_assets_count"]
    if count == 0:
        console.print("[bold green]✨ Tous les assets sont déjà parfaitement synchronisés avec les contrôles réglementaires.[/bold green]")
    else:
        console.print(f"[bold green]✅ {count} assets mis à jour avec leurs contrôles réglementaires correspondants.[/bold green]")
        for item in res["updated_assets"]:
            console.print(f"  • [cyan]{item['asset_id']}[/cyan] : +{item['added_controls']} (total: {item['total_controls']})")


@app.command(name="audit-compliance")
def audit_compliance_cmd(
    kb_dir: Path = typer.Option(
        Path("data/kb"),
        "--kb-dir",
        "-k",
        help="Répertoire racine de la base de connaissances.",
    ),
    framework: str = typer.Option(
        None,
        "--framework",
        "-f",
        help="Filtrer par référentiel spécifique (NIS2, SecNumCloud, ISO27001, 3GPP).",
    ),
) -> None:
    """Audite la couverture réglementaire et détecte les manques d'architecture (Gap Analysis)."""
    from rich.table import Table

    from pipelines.compliance_mapper import audit_compliance_gaps

    console.print(f"[bold blue]🛡️ Audit de conformité réglementaire (framework: {framework or 'TOUS'})...[/bold blue]")
    res = audit_compliance_gaps(kb_dir=kb_dir, framework=framework)

    table = Table(title="Couverture des Référentiels Réglementaires")
    table.add_column("Référentiel", style="cyan")
    table.add_column("Couverts / Total", style="magenta")
    table.add_column("Taux", style="green")
    table.add_column("Contrôles Orphelins (Gaps)", style="red")

    for fw, data in res["frameworks"].items():
        total = data["total"]
        cov = data["covered"]
        pct = f"{round((cov / total) * 100, 1)}%" if total > 0 else "0%"
        unc = ", ".join([c["id"] for c in data["uncovered_controls"]]) or "Aucun (100% couvert)"
        table.add_row(fw, f"{cov} / {total}", pct, unc)

    console.print(table)
    console.print(
        f"[bold]Couverture globale : {res['global_covered']}/{res['global_total']} ({res['global_coverage_percentage']} %)[/bold]"
    )


@app.command(name="shred-rfp")
def shred_rfp_cmd(
    rfp_file: Path = typer.Argument(..., help="Chemin vers le fichier RFP/CCTP brut ou Markdown."),
    engagement: str = typer.Option("demo-rfp-2026", "--engagement", "-e", help="Identifiant de l'engagement projet."),
    persist: bool = typer.Option(True, "--persist/--no-persist", help="Persister dans la base d'engagement locale."),
    output_json: Path = typer.Option(None, "--output-json", "-o", help="Chemin d'export JSON de la matrice."),
) -> None:
    """Déstructure un RFP en exigences atomiques et calcule la matrice de conformité triangulaire."""
    import json

    from rich.table import Table

    from pipelines.rfp_shredder import RFPShredder

    if not rfp_file.exists():
        console.print(f"[bold red]❌ Fichier introuvable : {rfp_file}[/bold red]")
        raise typer.Exit(code=1)

    text = rfp_file.read_text(encoding="utf-8")
    shredder = RFPShredder(kb_dir="data/kb")
    requirements = shredder.shred_text(text, engagement=engagement)
    res = shredder.build_compliance_matrix(requirements)

    console.print(f"\n[bold cyan]📑 RFP Déstructuré : {len(requirements)} exigences identifiées[/bold cyan]")
    console.print(f"Couverture KB standard : [bold green]{res['coverage_rate']} %[/bold green] ({res['covered']}/{res['total_requirements']})")
    console.print(f"Écarts identifiés (Gaps) : [bold red]{res['gaps']}[/bold red] | Partiel : [bold yellow]{res['partially_covered']}[/bold yellow]")

    table = Table(title=f"Matrice de Conformité RFP Triangulaire — {engagement}", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Catégorie", style="magenta")
    table.add_column("Statut", style="bold")
    table.add_column("Actifs KB", style="green")
    table.add_column("Contrôles", style="yellow")

    for r in requirements[:15]:
        status_style = "green" if r.status == "covered" else ("yellow" if r.status == "partially_covered" else "red")
        table.add_row(
            r.id,
            r.category,
            f"[{status_style}]{r.status}[/{status_style}]",
            ", ".join(r.matched_assets[:2]) or "-",
            ", ".join(r.matched_controls[:2]) or "-",
        )
    console.print(table)
    if len(requirements) > 15:
        console.print(f"... et {len(requirements) - 15} autres exigences.")

    if persist:
        from mcp_server.core.config import server_config
        eng_p = server_config.engagements_dir / f"{engagement}.lbug"
        shredder.persist_to_engagement(
            engagement=engagement,
            requirements=requirements,
            db_path=eng_p if eng_p.exists() else server_config.knowledge_db_path,
        )
        console.print(f"[bold green]💾 Exigences enregistrées dans le graphe d'engagement : {engagement}[/bold green]")

    if output_json:
        output_json.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[bold blue]Export JSON écrit : {output_json}[/bold blue]")


@app.command(name="zero-draft-hld")
def zero_draft_hld_cmd(
    engagement: str = typer.Option("demo-rfp-2026", "--engagement", "-e", help="Identifiant de l'engagement projet."),
    output_md: Path = typer.Option(None, "--output-md", "-o", help="Chemin du fichier Markdown HLD généré."),
    trigger_gaps: bool = typer.Option(False, "--trigger-gaps", help="Générer les questions d'élicitation pour les gaps."),
) -> None:
    """Génère le document HLD Zero-Draft et optionnellement les questions d'élicitation ciblées."""
    from mcp_server.core.config import server_config
    from tools.elicitation.zero_draft import ZeroDraftAssembler

    eng_p = server_config.engagements_dir / f"{engagement}.lbug"
    assembler = ZeroDraftAssembler(
        db_path=eng_p if eng_p.exists() else server_config.knowledge_db_path,
        kb_dir="data/kb",
    )
    result = assembler.generate_zero_draft_hld(engagement=engagement)

    console.print(f"\n[bold cyan]📄 Zero-Draft HLD généré pour l'engagement : {engagement}[/bold cyan]")
    console.print(f"Statut du document : [bold]{result['status'].upper()}[/bold]")
    console.print(f"Couverture standard : [bold green]{result['coverage_rate']} %[/bold green] ({result['covered_count']}/{result['total_requirements']})")
    console.print(f"Gaps résiduels : [bold red]{result['gap_count']}[/bold red]")

    out_file = output_md or Path(f"projects/{engagement}/HLD-zero-draft.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(result["document_markdown"], encoding="utf-8")
    console.print(f"[bold green]✅ Document HLD enregistré dans : {out_file}[/bold green]")

    if trigger_gaps:
        q_res = assembler.trigger_targeted_elicitation(engagement=engagement)
        console.print(f"[bold magenta]📬 {q_res['questions_created']} questions d'élicitation créées pour combler les gaps ![/bold magenta]")



def ingest_main() -> None:
    """Point d'entrée CLI direct pour l'ingestion."""
    typer.run(ingest)


def visualize_main() -> None:
    """Point d'entrée CLI direct pour la visualisation du graphe."""
    typer.run(visualize_cmd)


def main() -> None:
    """Point d'entrée CLI générique Typer."""
    app()


if __name__ == "__main__":
    main()




