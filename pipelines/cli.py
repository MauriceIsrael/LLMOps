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
        Path("data/kuzu_db"),
        "--db-path",
        "-d",
        help="Répertoire de stockage de la base Kùzu DB.",
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
        Path("data/kuzu_db"),
        "--db-path",
        "-d",
        help="Répertoire de stockage de la base Kùzu DB.",
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




