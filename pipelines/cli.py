"""CLI Typer pour lancer le pipeline d'ingestion de la base de connaissances dans Kùzu DB."""

from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import track
import typer

load_dotenv()

from pipelines.ingestion.graph_loader import KuzuGraphLoader
from pipelines.ingestion.llama_extractor import ArchitectureGraphExtractor
from pipelines.ingestion.markdown_parser import MarkdownDocParser

app = typer.Typer(
    help="CLI d'ingestion des documents d'architecture Markdown vers le Graphe de Connaissances Kùzu DB."
)
console = Console()


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
    console.print(f"[bold blue]🚀 Démarrage de l'ingestion depuis :[/bold blue] {kb_dir}")

    if not kb_dir.exists():
        console.print(f"[bold red]❌ Le répertoire {kb_dir} n'existe pas.[/bold red]")
        raise typer.Exit(code=1)

    md_files = list(kb_dir.rglob("*.md"))
    console.print(f"[bold green]📄 {len(md_files)} fichiers Markdown trouvés.[/bold green]")

    parser = MarkdownDocParser()
    extractor = ArchitectureGraphExtractor()
    loader = KuzuGraphLoader(db_path=db_path)

    total_nodes = 0
    total_rels = 0

    for file_path in track(md_files, description="Ingestion en cours..."):
        try:
            parsed_doc = parser.parse_file(file_path)
            nodes, rels = extractor.extract_nodes_and_relations(parsed_doc)
            loader.load_doc_nodes_and_rels(nodes, rels)
            total_nodes += len(nodes)
            total_rels += len(rels)
        except Exception as e:
            console.print(f"[bold yellow]⚠️ Erreur lors du traitement de {file_path.name} : {e}[/bold yellow]")

    console.print(
        f"[bold green]✅ Ingestion terminée avec succès ![/bold green]\n"
        f"📊 [bold]{total_nodes}[/bold] nœuds et [bold]{total_rels}[/bold] relations enregistrés dans [bold]{db_path}[/bold]."
    )


def main() -> None:
    typer.run(ingest)


if __name__ == "__main__":
    main()


