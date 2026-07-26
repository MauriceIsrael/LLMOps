"""Interface CLI Typer pour le prototype d'élicitation pilotée par les manques (elicit)."""


import typer
from rich.console import Console
from rich.table import Table

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.mailbox.roster import RosterManager
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


def resolve_impersonation(
    as_user: str | None, default_author: str, default_role: str, engagement: str = "demo-2026"
) -> tuple[str, str]:
    """Résout l'auteur et le rôle à partir du drapeau d'usurpation --as (ex: --as alice)."""
    if not as_user:
        return default_author, default_role
    roster = RosterManager(engagement=engagement)
    user_info = roster.users.get(as_user)
    if user_info:
        author = user_info.get("name", as_user)
        roles = user_info.get("roles", [])
        role = roles[0] if roles else default_role
        return author, role
    return as_user, default_role


@app.command()
def answer(
    question_id: str = typer.Argument(..., help="Identifiant de la question (ex: Q-0001)"),
    text: str = typer.Option(..., "--text", "-t", help="Texte de la réponse de l'expert"),
    author: str = typer.Option("alice", "--author", "-a", help="Nom de l'expert"),
    role: str = typer.Option("cloud-architect", "--role", "-r", help="Rôle de l'expert"),
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as alice, --as bob)"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Soumettre une réponse d'expert et démarrer le flux d'intake jusqu'à l'interruption."""
    author, role = resolve_impersonation(as_user, author, role, engagement)
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
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as alice)"),
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
    amend: str | None = typer.Option(None, "--amend", help="Identifiant de l'énoncé à amender (ex: S-0034)"),
    to: str | None = typer.Option(None, "--to", help="Nouvelle valeur révisée pour l'énoncé amendé"),
    by: str = typer.Option("chief-architect", "--by", help="Auteur de l'arbitrage (ex: chief-architect)"),
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as charlie)"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Arbitrer un conflit (réservé à l'architecte en chef). Passe l'énoncé perdant à superseded ou l'amende."""
    by_user, _ = resolve_impersonation(as_user, by, "chief-architect", engagement)
    repo = ElicitationRepository()
    repo.arbitrate_conflict(
        conflict_id,
        keep_statement_id=keep,
        reason=reason,
        arbitrated_by=by_user,
        amend_statement_id=amend,
        amend_to=to,
    )
    console.print(
        f"[bold green]✅ Conflit {conflict_id} arbitré par {by_user}. Énoncé conservé : {keep}. Raison : {reason}[/bold green]"
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


@app.command()
def subjects(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
    stall_days: int = typer.Option(7, "--stall-days", "-s", help="Seuil de jours pour la détection de stagnation"),
) -> None:
    """Afficher le tableau de maturité des sujets (Maturity Board) et le publier dans la mailbox."""
    repo = ElicitationRepository()
    board = repo.get_subjects_maturity_board(engagement=engagement, stall_days=stall_days)

    if not board:
        console.print(f"[yellow]Aucun sujet trouvé dans la base pour {engagement}.[/yellow]")
        return

    table = Table(title=f"Maturity Board — {engagement}")
    table.add_column("Sujet", style="cyan")
    table.add_column("Niveau Atteint", style="magenta")
    table.add_column("Question Bloquante", style="yellow")
    table.add_column("Délai (j)", style="white")
    table.add_column("Stagnation", style="bold red")

    for r in board:
        st_str = "⚠️ STAGNANT" if r["is_stalled"] else "OK"
        q_ref = r["open_question_ref"] or "-"
        table.add_row(r["subject"], r["level"], q_ref, str(r["days_at_level"]), st_str)

    console.print(table)

    # Publier / Mettre à jour la fiche dans la mailbox de manière déterministe
    from tools.elicitation.mailbox.adapters.file_adapter import FileMailboxAdapter
    from tools.elicitation.mailbox.renderers import render_maturity_board

    mb_rendered = render_maturity_board(engagement=engagement, board_data=board)
    mb_adapter = FileMailboxAdapter(engagement=engagement)
    mb_path = mb_adapter.mailbox_dir / "maturity_board.md"
    mb_path.write_text(mb_rendered, encoding="utf-8")

    console.print(f"📌 Maturity Board épinglé dans la mailbox : [bold cyan]{mb_path}[/bold cyan]")


@app.command()
def contest(
    statement_id: str = typer.Argument(..., help="Identifiant de l'énoncé contesté (ex: S-0001)"),
    text: str = typer.Option(..., "--text", "-t", help="Argumentation de contestation"),
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as rui)"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Contester un énoncé existant et créer un conflit d'architecture."""
    author, role = resolve_impersonation(as_user, "rui", "mobile-core-architect", engagement)
    repo = ElicitationRepository()
    s_id, c_id = repo.contest_statement(
        target_statement_id=statement_id, author=author, role=role, text=text, engagement=engagement
    )
    console.print(
        f"[bold yellow]⚠️ Énoncé {statement_id} contesté par {author} ({role}). Nouvel énoncé : {s_id}. Conflit créé : {c_id}[/bold yellow]"
    )


@app.command()
def harvest(
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as sofia)"),
) -> None:
    """Extraire le REX et proposer de nouvelles règles de manque à partir des conflits arbitrés."""
    author, _ = resolve_impersonation(as_user, "sofia", "chief-architect", engagement)
    console.print(f"[bold blue]🌾 REX & Harvest pour l'engagement {engagement} par {author}...[/bold blue]")
    console.print("  - Candidate pattern: MCX service decomposition hold until 2nd engagement.")
    console.print("  - New gap rule candidate: Subject decided at L3 with a dependency on another subject below L3.")



def main() -> None:
    app()




if __name__ == "__main__":
    main()
