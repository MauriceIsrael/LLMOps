"""Interface CLI Typer pour le prototype d'élicitation pilotée par les manques (elicit)."""

import typer
from rich.console import Console
from rich.table import Table

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.repository import ElicitationRepository

app = typer.Typer(help="CLI d'élicitation d'architecture pilotée par les manques (Gap-Driven Elicitation).")
console = Console()


@app.command()
def scan(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement projet"),
    max_questions: int = typer.Option(8, "--max-questions", "-m", help="Nombre maximal de questions à émettre"),
) -> None:
    """Détecte les manques (gaps) du projet et émet des questions aux experts."""
    console.print(f"[bold blue]🔎 Scan des manques pour l'engagement : {engagement}...[/bold blue]")

    graph = build_scan_graph()
    initial_state = {"engagement": engagement, "max_questions": max_questions}
    result = graph.invoke(initial_state)

    questions = result.get("questions", [])
    _dispatched = result.get("dispatched", [])

    console.print(

        f"[bold green]✅ Scan terminé avec succès ! {len(questions)} question(s) générée(s) et postée(s).[/bold green]"
    )

    table = Table(title=f"Questions Émises — {engagement}")
    table.add_column("ID", style="cyan")
    table.add_column("Section", style="magenta")
    table.add_column("Rôle Cible", style="yellow")
    table.add_column("Question", style="white")

    for q in questions:
        table.add_row(q["id"], q["section"], q["routed_to"], q["question"])

    console.print(table)


@app.command()
def questions(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement projet"),
    status: str = typer.Option("sent", "--status", "-s", help="Statut des questions (open, sent, confirmed, declined)"),
) -> None:
    """Lister les questions de l'engagement par statut."""
    db_client = KuzuClient()
    query = f"MATCH (q:Question {{engagement: '{engagement}', status: '{status}'}}) RETURN q.id as id, q.section as section, q.question as question, q.routed_to as routed_to;"
    rows = db_client.execute_cypher(query)

    if not rows or "error" in rows[0]:
        console.print(f"[yellow]Aucune question avec le statut '{status}' trouvée pour {engagement}.[/yellow]")
        return

    table = Table(title=f"Questions ({status}) — {engagement}")
    table.add_column("ID", style="cyan")
    table.add_column("Section", style="magenta")
    table.add_column("Rôle Cible", style="yellow")
    table.add_column("Question", style="white")

    for r in rows:
        table.add_row(r["id"], r["section"], r["routed_to"], r["question"])

    console.print(table)


@app.command()
def answer(
    question_id: str = typer.Argument(..., help="Identifiant de la question (ex: Q-0001)"),
    text: str = typer.Option(..., "--text", "-t", help="Texte de la réponse de l'expert"),
    author: str = typer.Option("alice", "--author", "-a", help="Nom de l'expert"),
    role: str = typer.Option("cloud-architect", "--role", "-r", help="Rôle de l'expert"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Soumettre une réponse d'expert et démarrer le flux d'intake jusqu'à l'interruption."""
    console.print(f"[bold blue]💬 Soumission de la réponse pour {question_id} par {author} ({role})...[/bold blue]")

    checkpointer = get_sqlite_checkpointer(engagement=engagement)
    graph = build_intake_graph(checkpointer=checkpointer)

    thread_config = {"configurable": {"thread_id": question_id}}
    initial_state = {
        "question_id": question_id,
        "answer_text": text,
        "author": author,
        "role": role,
        "engagement": engagement,
    }

    # Exécution du flux jusqu'à l'interrupt
    events = graph.invoke(initial_state, config=thread_config)

    console.print(f"[bold yellow]⏸️ Flux en pause à l'étape 'confirm' (interrupt) pour {question_id}.[/bold yellow]")
    console.print("Énoncés candidats proposés pour confirmation :")
    candidates = events.get("candidate_statements", [])
    for c in candidates:
        console.print(f"  - Subject: [cyan]{c['subject']}[/cyan] | Predicate: [magenta]{c['predicate']}[/magenta] | Value: [white]{c['value']}[/white] | Confidence: [yellow]{c['confidence']}[/yellow]")

    console.print(f"\nPour confirmer et enregistrer : [bold green]poetry run elicit confirm {question_id} --accept[/bold green]")


@app.command()
def confirm(
    question_id: str = typer.Argument(..., help="Identifiant de la question en pause"),
    accept: bool = typer.Option(True, "--accept/--reject", help="Accepter ou rejeter les énoncés"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Reprendre un flux en pause (interrupt) et persister les énoncés dans un nouveau processus."""
    console.print(f"[bold blue]▶️ Reprise du flux pour {question_id} (Accept: {accept})...[/bold blue]")

    checkpointer = get_sqlite_checkpointer(engagement=engagement)
    graph = build_intake_graph(checkpointer=checkpointer)
    thread_config = {"configurable": {"thread_id": question_id}}

    decision = {"action": "accept" if accept else "reject", "accept": accept}

    # Reprise à partir de la primitive Command(resume=...) de LangGraph
    from langgraph.types import Command

    result = graph.invoke(Command(resume=decision), config=thread_config)

    if result.get("rejected"):
        console.print(f"[bold red]❌ Les énoncés pour {question_id} ont été rejetés. Aucun énoncé n'a été enregistré.[/bold red]")
    else:
        p_ids = result.get("persisted_statement_ids", [])
        c_ids = result.get("created_conflict_ids", [])
        console.print(f"[bold green]✅ Flux terminé ! Énoncés enregistrés : {p_ids}[/bold green]")
        if c_ids:
            console.print(f"[bold red]⚠️ Conflits générés suite à une contradiction : {c_ids}[/bold red]")


@app.command()
def conflicts(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Lister tous les conflits ouverts d'un engagement."""
    repo = ElicitationRepository()
    c_list = repo.get_conflicts(engagement, status="open")

    if not c_list:
        console.print(f"[bold green]✅ Aucun conflit ouvert pour l'engagement {engagement}.[/bold green]")
        return

    table = Table(title=f"Conflits Ouverts — {engagement}")
    table.add_column("ID Conflit", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Détail", style="white")

    for c in c_list:
        table.add_row(c["id"], c["kind"], c["detail"])

    console.print(table)


@app.command()
def arbitrate(
    conflict_id: str = typer.Argument(..., help="Identifiant du conflit (ex: C-0001)"),
    keep: str = typer.Option(..., "--keep", "-k", help="Identifiant de l'énoncé à conserver (ex: S-0001)"),
    reason: str = typer.Option(..., "--reason", "-r", help="Raison de l'arbitrage"),
    by: str = typer.Option("chief-architect", "--by", help="Auteur de l'arbitrage (ex: chief-architect)"),
) -> None:
    """Arbitrer un conflit (réservé à l'architecte en chef). Passe l'énoncé perdant à superseded."""
    repo = ElicitationRepository()
    repo.arbitrate_conflict(conflict_id, keep_statement_id=keep, reason=reason, arbitrated_by=by)
    console.print(
        f"[bold green]✅ Conflit {conflict_id} arbitré par {by}. Énoncé conservé : {keep}. Raison : {reason}[/bold green]"
    )


@app.command()
def assemble(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Assembler le document d'architecture final et émettre le rapport de statut."""
    console.print(f"[bold blue]📑 Assemblage du document pour l'engagement {engagement}...[/bold blue]")

    graph = build_assemble_graph()
    result = graph.invoke({"engagement": engagement})

    doc_path = result.get("document_path")
    status = result.get("status")
    conflicts_count = len(result.get("open_conflicts", []))

    if status == "PROVISIONAL":
        console.print(
            f"[bold yellow]⚠️ Document assemblé avec statut PROVISIONAL ! ({conflicts_count} conflit(s) ouvert(s)).[/bold yellow]"
        )
    else:
        console.print("[bold green]✅ Document assemblé avec succès avec statut COMPLETE ![/bold green]")

    console.print(f"📄 Chemin du document généré : [bold cyan]{doc_path}[/bold cyan]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
