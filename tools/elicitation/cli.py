"""Interface CLI Typer pour le prototype d'élicitation pilotée par les manques (elicit)."""


import typer
from rich.console import Console
from rich.table import Table

from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.mailbox.roster import RosterManager
from tools.elicitation.repository import ElicitationRepository

app = typer.Typer(help="CLI d'élicitation d'architecture pilotée par les manques (Gap-Driven Elicitation).")
console = Console()


@app.command()
def plan(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement projet"),
    blueprint_path: str = typer.Option("data/kb/blueprints/BLU-hla-mcx.yaml", "--blueprint", "-b", help="Fichier blueprint structuré"),
) -> None:
    """Affiche le plan d'instructions complet (Instruction Plan) à 4 blocs selon SPEC-PLANNING-AND-DEMO."""
    from tools.elicitation.plan import generate_instruction_plan, render_plan_cli
    plan_data = generate_instruction_plan(engagement=engagement, blueprint_path=blueprint_path)
    render_plan_cli(plan_data)


@app.command()
def scan(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement projet"),
    blueprint: str = typer.Option("BLU-hla-mcx", "--blueprint", "-b", help="Identifiant ou chemin du blueprint d'architecture"),
    max_questions: int = typer.Option(8, "--max-questions", "-m", help="Nombre maximal de questions à émettre"),
    strategy: str = typer.Option("breadth", "--strategy", help="Stratégie de dispatch : breadth (défaut pour BID) ou depth (pour BUILD)"),
) -> None:
    """Détecte les manques (gaps) du projet et émet des questions aux experts."""
    console.print(f"[bold blue]🔎 Scan des manques pour l'engagement : {engagement} (blueprint: {blueprint}, stratégie: {strategy})...[/bold blue]")

    graph = build_scan_graph()
    initial_state = {
        "engagement": engagement,
        "blueprint_id": blueprint,
        "max_questions": max_questions,
        "strategy": strategy,
    }
    result = graph.invoke(initial_state)

    questions = result.get("questions", [])
    counts = result.get("counts_summary", {})

    console.print(
        f"[bold green]✅ Scan terminé ! Nouveaux: {counts.get('new', 0)} · Ouverts: {counts.get('open', 0)} · Retenus prématurés: {counts.get('held_premature', 0)} · Retenus file d'attente: {counts.get('held_queued', 0)}[/bold green]"
    )

    table = Table(title=f"Questions Émises — {engagement}")
    table.add_column("ID", style="cyan")
    table.add_column("Section", style="magenta")
    table.add_column("Rôle Cible", style="yellow")
    table.add_column("Question", style="white")

    for q in questions:
        table.add_row(q["id"], q["section"], q["routed_to"], q["question"])

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
    question_id: str | None = typer.Argument(None, help="Identifiant de la question (ex: Q-0001)"),
    text: str | None = typer.Option(None, "--text", "-t", help="Texte de la réponse de l'expert"),
    from_file: str | None = typer.Option(None, "--from-file", help="Fichier carte Markdown contenant la réponse"),
    author: str = typer.Option("alice", "--author", "-a", help="Nom de l'expert"),
    role: str = typer.Option("cloud-architect", "--role", "-r", help="Rôle de l'expert"),
    as_user: str | None = typer.Option(None, "--as", help="Usurper un utilisateur du roster (ex: --as alice, --as rui)"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Soumettre une réponse d'expert (directe ou depuis un fichier carte .md) et démarrer le flux d'intake."""
    from pathlib import Path

    if from_file:
        filepath = Path(from_file)
        if not filepath.exists():
            console.print(f"[bold red]Fichier introuvable : {from_file}[/bold red]")
            return
        content = filepath.read_text(encoding="utf-8")
        
        # Extraire l'ID de question depuis le nom de fichier ou le header
        if not question_id:
            question_id = filepath.stem.split(".")[0]
        
        # Extraire le texte de réponse sous "## Your answer"
        if "## Your answer" in content:
            ans_part = content.split("## Your answer", 1)[1]
            if "## How to submit" in ans_part:
                ans_part = ans_part.split("## How to submit", 1)[0]
            text = ans_part.strip()
        else:
            text = content.strip()

    if not question_id or not text:
        console.print("[bold red]Erreur : question_id et text (ou --from-file) sont requis.[/bold red]")
        return
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
@app.command()
def subject(
    name: str = typer.Argument(..., help="Nom du sujet canonique (ex: floor-control)"),
    trajectory: bool = typer.Option(True, "--trajectory", help="Aicher la trajectoire de maturité chronologique du sujet"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Affiche la trajectoire de maturité d'un sujet (questions et énoncés chronologiques)."""
    from tools.elicitation.trajectory import get_subject_trajectory, render_trajectory_cli
    traj = get_subject_trajectory(subject_name=name, engagement=engagement)
    render_trajectory_cli(traj)


@app.command()
def demote(
    subject_name: str = typer.Argument(..., help="Nom du sujet à rétrograder"),
    to: str = typer.Option("L2_decomposed", "--to", help="Niveau de cible après rétrogradation (ex: L2_decomposed)"),
    as_user: str | None = typer.Option(None, "--as", help="Auteur de la rétrogradation (ex: --as sofia)"),
    reason: str = typer.Option(..., "--reason", "-r", help="Raison explicite de la rétrogradation"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Rétrograde la maturité d'un sujet (demotion non-monotone) et réouvre les questions fermées."""
    author, _ = resolve_impersonation(as_user, "sofia", "chief-architect", engagement)
    repo = ElicitationRepository()
    repo.demote_subject(subject_name=subject_name, to_level=to, author=author, reason=reason, engagement=engagement)
    console.print(f"[bold yellow]⚠️ Sujet '{subject_name}' rétrogradé à {to} par {author}. Raison : {reason}[/bold yellow]")
    console.print("Énoncés de niveau supérieur marqués en 'under_review'. Questions réouvertes.")


@app.command()
def submit(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
    as_user: str = typer.Option("external:m.okonkwo", "--as", help="Identifiant du contributeur externe (ex: --as external:m.okonkwo)"),
    title: str = typer.Option(..., "--title", help="Titre explicatif du matériel proposé"),
    material: str = typer.Option(..., "--material", help="Texte ou chemin vers le fichier de matériel"),
    attach: str | None = typer.Option(None, "--attach", help="Diagramme ou preuve jointe (optionnel)"),
    relates_to: str | None = typer.Option(None, "--relates-to", help="Sujet associé à titre indicatif"),
) -> None:
    """Soumettre une contribution spontanée externe en staging sans écriture directe dans le graphe."""
    from pathlib import Path

    from tools.elicitation.contribution_repository import ContributionRepository

    mat_text = material
    if Path(material).exists():
        mat_text = Path(material).read_text(encoding="utf-8")

    crepo = ContributionRepository(engagement=engagement)
    c = crepo.submit(contributor=as_user, title=title, material_text=mat_text, attachment_path=attach, relates_to=relates_to)
    console.print(f"[bold green]📥 Contribution {c.id} soumise avec succès par {as_user} ! Status: {c.status}[/bold green]")
    console.print("En attente de tri par l'architecte lead (elicit triage).")


@app.command()
def contributions(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
    status: str | None = typer.Option(None, "--status", help="Filtrer par statut (submitted, triaged, accepted, declined)"),
) -> None:
    """Lister les contributions spontanées de l'engagement."""
    from tools.elicitation.contribution_repository import ContributionRepository
    crepo = ContributionRepository(engagement=engagement)
    items = crepo.list_all(status=status)

    if not items:
        console.print(f"[yellow]Aucune contribution spontanée trouvée pour {engagement}.[/yellow]")
        return

    table = Table(title=f"Contributions Spontanées — {engagement}")
    table.add_column("ID", style="cyan")
    table.add_column("Contributeur", style="magenta")
    table.add_column("Titre", style="white")
    table.add_column("Statut", style="bold yellow")

    for c in items:
        table.add_row(c.id, c.contributor, c.title, c.status)

    console.print(table)


@app.command()
def triage(
    contribution_id: str = typer.Argument(..., help="Identifiant de la contribution (ex: CT-0001)"),
    as_user: str = typer.Option("sofia", "--as", help="Architecte lead effectuant le tri (ex: --as sofia)"),
    accept: bool = typer.Option(True, "--accept/--decline", help="Accepter ou refuser le tri de la contribution"),
    reason: str = typer.Option("", "--reason", help="Raison en cas de refus ou de réorientation"),
    to_subject: str | None = typer.Option(None, "--to-subject", help="Sujet canonique cible"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Effectuer le tri d'une contribution spontanée par l'architecte lead."""
    from tools.elicitation.contribution_repository import ContributionRepository
    crepo = ContributionRepository(engagement=engagement)
    decision = "accept" if accept else "decline"
    c = crepo.triage(ct_id=contribution_id, lead_author=as_user, decision=decision, reason=reason, to_subject=to_subject)
    console.print(f"[bold green]✅ Contribution {c.id} triée par {as_user}. Décision : {decision}. Statut : {c.status}[/bold green]")


@app.command()
def crystallise(
    contribution_id: str = typer.Argument(..., help="Identifiant de la contribution (ex: CT-0001)"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Formuler les énoncés candidats et cartographier le vocabulaire d'une contribution triée."""
    from tools.elicitation.contribution_repository import ContributionRepository
    crepo = ContributionRepository(engagement=engagement)
    c = crepo.crystallise(ct_id=contribution_id)
    console.print(f"[bold blue]💎 Contribution {c.id} cristallisée ! Sujets cartographiés : {c.mapped_subjects}[/bold blue]")
    if c.unmapped_terms:
        console.print(f"[bold yellow]⚠️ Termes non cartographiés proposés : {c.unmapped_terms}[/bold yellow]")


@app.command()
def confirm_contribution(
    contribution_id: str = typer.Argument(..., help="Identifiant de la contribution (ex: CT-0001)"),
    as_user: str = typer.Option(..., "--as", help="Auteur de la contribution confirmant le sens (ex: --as external:m.okonkwo)"),
    accept: bool = typer.Option(True, "--accept/--reject", help="Confirmer ou rejeter la fidélité du sens extrait"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Confirmation du SENS par l'auteur d'une contribution externe."""
    from tools.elicitation.contribution_repository import ContributionRepository
    crepo = ContributionRepository(engagement=engagement)
    c = crepo.confirm_by_author(ct_id=contribution_id, author=as_user, accept=accept)
    console.print(f"[bold green]✍️ Sens confirmé par l'auteur {as_user} pour {c.id}. Statut : {c.status}[/bold green]")


@app.command()
def accept(
    contribution_id: str = typer.Argument(..., help="Identifiant de la contribution (ex: CT-0001)"),
    as_user: str = typer.Option("sofia", "--as", help="Architecte lead validant l'entrée dans le graphe (ex: --as sofia)"),
    section: str = typer.Option("4.5", "--section", help="Section documentaire cible"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Validation finale de l'ENTRÉE dans le graphe par l'architecte lead."""
    from tools.elicitation.contribution_repository import ContributionRepository
    crepo = ContributionRepository(engagement=engagement)
    c, p_ids = crepo.accept_by_lead(ct_id=contribution_id, lead_author=as_user, section_id=section)
    console.print(f"[bold green]🎉 Contribution {c.id} acceptée par {as_user} ! Énoncés enregistrés dans Kùzu DB : {p_ids}[/bold green]")




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
    notify: bool = typer.Option(True, "--notify/--no-notify", help="Notifier le propriétaire du Knowledge Hub (Maurice)"),
) -> None:
    """Extraire le REX et proposer de nouvelles règles de manque à partir des conflits arbitrés."""
    author, role = resolve_impersonation(as_user, "sofia", "chief-architect", engagement)
    console.print(f"[bold blue]🌾 REX & Harvest pour l'engagement {engagement} par {author} ({role})...[/bold blue]")

    from tools.elicitation.flows.harvest import build_harvest_graph
    flow = build_harvest_graph()
    state = flow.invoke({"engagement": engagement, "by": author})
    candidates = state.get("promotion_candidates", [])

    if not candidates:
        console.print("[dim]Aucun nouveau candidat détecté pour l'instant.[/dim]")
        return

    for c in candidates:
        console.print(f"  - [green]Candidat trouvé :[/green] [bold]{c['title']}[/bold] ({c['kind']})")
        console.print(f"    [italic]{c['why']}[/italic]")
        if notify:
            from mcp_server.core.notifier import notify_owner_of_suggestion
            notif = notify_owner_of_suggestion(
                title=f"Harvest REX: {c['title']}",
                rationale=c["why"],
                suggested_change=f"Pattern ou règle candidate issue de l'engagement {engagement} ({c['kind']}). Source: {c.get('source')}.",
                author=f"{author} ({role})",
                contact="maurice.israel@free.fr",
                source_engagement=engagement,
            )
            console.print(f"    📢 [bold cyan]Notification propriétaire envoyée :[/bold cyan] ID {notif['suggestion_id']} ({', '.join(notif['notifications_sent'])})")




@app.command()
def publish(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Engagement identifier to publish"),
    db_path: str | None = typer.Option(None, "--db-path", "-d", help="Optional working database source path"),
) -> None:
    """Takes a consistent snapshot of the working graph and installs it atomically at data/engagements/<id>.kuzu."""
    import shutil
    from pathlib import Path

    from mcp_server.core.db import get_engagement_path, validate_engagement_id
    from tools.elicitation.db_schema import ElicitationSchemaInitializer

    valid_id = validate_engagement_id(engagement)
    target_path = get_engagement_path(valid_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path and Path(db_path).exists():
        src = Path(db_path)
    else:
        art_path = Path("artifacts") / valid_id / "graph"
        if art_path.exists():
            src = art_path
        elif target_path.exists():
            src = target_path
        else:
            src = None

    if src and src != target_path:
        console.print(f"[bold blue]📦 Publishing engagement snapshot for {valid_id} from {src}...[/bold blue]")
        tmp_target = target_path.parent / f"{valid_id}.tmp.kuzu"
        if tmp_target.exists():
            shutil.rmtree(tmp_target)

        shutil.copytree(src, tmp_target)

        schema_init = ElicitationSchemaInitializer(db_path=tmp_target)
        del schema_init

        if target_path.exists():
            shutil.rmtree(target_path)
        tmp_target.rename(target_path)
    else:
        schema_init = ElicitationSchemaInitializer(db_path=target_path)
        del schema_init

    console.print(f"[bold green]✅ Engagement {valid_id} published successfully to {target_path}![/bold green]")


@app.command(name="import")
def import_data(
    file_path: str = typer.Argument(..., help="Path to JSON import file"),
    engagement: str = typer.Option("demo-2026", "--engagement", "-e", help="Identifier of engagement target"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and report without writing to database"),
) -> None:
    """Import third-party elicitation payload (Subjects, Statements, Conflicts, Uncertainties) via Repository pipeline."""
    import json
    from pathlib import Path

    p = Path(file_path)
    if not p.exists():
        console.print(f"[bold red]File not found: {file_path}[/bold red]")
        return

    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"[bold red]Invalid JSON file: {e}[/bold red]")
        return

    target_engagement = payload.get("engagement") or engagement
    console.print(f"[bold blue]📥 Import payload for engagement {target_engagement} (dry-run: {dry_run})...[/bold blue]")

    statements = payload.get("statements", [])
    subjects = payload.get("subjects", [])
    conflicts = payload.get("conflicts", [])
    uncertainties = payload.get("uncertainties", [])

    console.print(f"  - Subjects to import: {len(subjects)}")
    console.print(f"  - Statements to import: {len(statements)}")
    console.print(f"  - Conflicts to import: {len(conflicts)}")
    console.print(f"  - Uncertainties to import: {len(uncertainties)}")

    if dry_run:
        console.print("[bold yellow]🔍 Dry-run complete. No changes written to database.[/bold yellow]")
        return

    repo = ElicitationRepository()
    for s in subjects:
        repo.save_subject(s["name"], engagement=target_engagement, definition=s.get("definition", ""))
        if "level" in s:
            repo.advance_subject_level(s["name"], s["level"], engagement=target_engagement)

    persisted_stmt_ids = []
    for stmt in statements:
        stmt["engagement"] = target_engagement
        stmt_id = repo.save_statement(stmt)
        persisted_stmt_ids.append(stmt_id)

    console.print(f"[bold green]✅ Import complete for engagement {target_engagement}! Statements saved: {len(persisted_stmt_ids)}[/bold green]")


engagement_app = typer.Typer(help="Engagement lifecycle commands (create, archive).")
app.add_typer(engagement_app, name="engagement")


@engagement_app.command(name="create")
def engagement_create(
    engagement_id: str = typer.Argument(..., help="Identifier for new engagement (e.g. nordwave-mcx-2027)"),
) -> None:
    """Creates a new empty engagement database with engagement schema."""
    from mcp_server.core.db import get_engagement_path, validate_engagement_id
    from tools.elicitation.db_schema import ElicitationSchemaInitializer

    valid_id = validate_engagement_id(engagement_id)
    target_path = get_engagement_path(valid_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        console.print(f"[yellow]Engagement database {valid_id} already exists at {target_path}.[/yellow]")
        return

    schema_init = ElicitationSchemaInitializer(db_path=target_path)
    del schema_init
    console.print(f"[bold green]✨ Engagement database '{valid_id}' created successfully at {target_path}![/bold green]")


@engagement_app.command(name="archive")
def engagement_archive(
    engagement_id: str = typer.Argument(..., help="Identifier of engagement to archive"),
) -> None:
    """Archives an active engagement database by moving it to data/engagements/archive/."""
    import shutil

    from mcp_server.core.db import get_engagement_path, validate_engagement_id

    valid_id = validate_engagement_id(engagement_id)
    source_path = get_engagement_path(valid_id)
    if not source_path.exists():
        console.print(f"[bold red]❌ Engagement database '{valid_id}' not found at {source_path}.[/bold red]")
        return

    archive_dir = source_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target_path = archive_dir / source_path.name

    if target_path.exists():
        shutil.rmtree(target_path)

    shutil.move(str(source_path), str(target_path))
    console.print(f"[bold green]📦 Engagement '{valid_id}' archived successfully to {target_path}![/bold green]")


staff_app = typer.Typer(name="staff", help="Gestion des collaborateurs et compétences du projet")
app.add_typer(staff_app, name="staff")


@staff_app.command(name="add-skill")
def staff_add_skill(
    user: str = typer.Option(..., "--user", "-u", help="Login du collaborateur"),
    skill: str = typer.Option(..., "--skill", "-s", help="Identifiant de la compétence (ex: SKL-CRYPTO-HSM)"),
    level: str = typer.Option("senior", "--level", "-l", help="Niveau d'expertise (novice, intermediate, senior, expert)"),
    evidence: str = typer.Option("Attestation d'expérience / formation", "--evidence", help="Preuve d'expertise"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Ajouter une compétence vérifiée à un profil du roster."""
    from tools.elicitation.mailbox.roster import RosterManager
    mgr = RosterManager(engagement=engagement)
    ok = mgr.add_skill(user, skill, level=level, evidence=evidence)
    if ok:
        console.print(f"[bold green]✅ Compétence '{skill}' ({level}) attribuée à '{user}' pour l'engagement '{engagement}' ![/bold green]")
    else:
        console.print(f"[bold yellow]⚠️ Impossible d'ajouter la compétence : utilisateur '{user}' introuvable ou compétence déjà détenue.[/bold yellow]")


@staff_app.command(name="assign")
def staff_assign(
    user: str = typer.Option(..., "--user", "-u", help="Login du collaborateur"),
    name: str | None = typer.Option(None, "--name", "-n", help="Nom complet du collaborateur"),
    role: str = typer.Option("architect", "--role", "-r", help="Rôle principal"),
    skills: str = typer.Option("", "--skills", "-k", help="Compétences séparées par des virgules (ex: SKL-1,SKL-2)"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Affecter un nouveau collaborateur au projet avec ses rôles et compétences."""
    from tools.elicitation.mailbox.roster import RosterManager
    mgr = RosterManager(engagement=engagement)
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    mgr.assign_user(user, name=name, roles=[role], skills=skill_list)
    console.print(f"[bold green]✅ Collaborateur '{user}' affecté à '{engagement}' (Rôle: {role}, Compétences: {skill_list}) ![/bold green]")


@staff_app.command(name="contract-expertise")
def staff_contract_expertise(
    skill: str = typer.Option(..., "--skill", "-s", help="Identifiant de la compétence externalisée"),
    provider: str = typer.Option(..., "--provider", "-p", help="Nom du cabinet ou prestataire"),
    ref: str = typer.Option(..., "--ref", help="Référence du bon de commande ou contrat"),
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
) -> None:
    """Enregistrer une prestation d'assistance technique ou expertise externe."""
    from tools.elicitation.mailbox.roster import RosterManager
    mgr = RosterManager(engagement=engagement)
    mgr.contract_expertise(skill_id=skill, provider=provider, ref=ref)
    console.print(f"[bold green]✅ Prestation enregistrée pour la compétence '{skill}' auprès de '{provider}' (Réf: {ref}) pour '{engagement}' ![/bold green]")


@app.command(name="audit-skills")
def audit_skills(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement"),
    blueprint_path: str = typer.Option("data/kb/blueprints/BLU-hla-mcx.yaml", "--blueprint", "-b", help="Chemin vers le blueprint"),
) -> None:
    """Auditer la couverture des compétences requises par le Blueprint face aux profils de l'équipe."""
    from rich.table import Table

    from tools.elicitation.mailbox.roster import RosterManager
    from tools.elicitation.models.blueprint_schema import load_blueprint

    bp = load_blueprint(blueprint_path)
    mgr = RosterManager(engagement=engagement)
    covered = mgr.get_all_covered_skills()

    required_skills_map: dict[str, list[str]] = {}
    all_required: set[str] = set()
    for sec in bp.sections:
        s_skills = getattr(sec, "required_skills", [])
        if s_skills:
            required_skills_map[f"{sec.id} - {sec.title}"] = s_skills
            all_required.update(s_skills)

    if not all_required:
        console.print("[bold yellow]Aucune compétence requise spécifiée dans ce blueprint.[/bold yellow]")
        return

    uncovered = all_required - covered
    coverage_pct = round((len(all_required - uncovered) / len(all_required)) * 100, 1)

    table = Table(title=f"🎯 Matrice de Couverture des Compétences — Engagement {engagement}")
    table.add_column("Section Blueprint", style="cyan")
    table.add_column("Compétences Requises", style="magenta")
    table.add_column("Statut Couverture", style="bold")
    table.add_column("Affectation / Prestataire", style="green")

    for sec_name, skills in required_skills_map.items():
        missing_in_sec = [s for s in skills if s not in covered]
        if not missing_in_sec:
            status = "[green]COUVERT[/green]"
            holders = []
            for s in skills:
                for login, u in mgr.users.items():
                    if s in u.get("skills", []):
                        holders.append(f"{login} ({s})")
            contractors = [f"{c['provider']} ({c['skill']})" for c in mgr.external_contractors if c.get("skill") in skills]
            assignment = ", ".join(holders + contractors) or "Équipe interne"
        else:
            status = f"[red]MANQUANT ({', '.join(missing_in_sec)})[/red]"
            assignment = "[bold red]⚠️ Non pourvu (Action requise)[/bold red]"
        table.add_row(sec_name, ", ".join(skills), status, assignment)

    console.print(table)

    risk_level = "[bold green]FAIBLE[/bold green]" if coverage_pct == 100 else ("[bold yellow]MODÉRÉ[/bold yellow]" if coverage_pct >= 75 else "[bold red]CRITIQUE[/bold red]")
    console.print(f"\n📊 [bold]Taux de couverture global :[/bold] {coverage_pct}% ({len(all_required - uncovered)}/{len(all_required)} expertises)")
    console.print(f"⚠️ [bold]Index de risque de staffing :[/bold] {risk_level}")
    if uncovered:
        console.print(f"[bold red]❌ Compétences critiques à pourvoir :[/bold red] {', '.join(uncovered)}")
        console.print("[italic dim]Utilisez 'elicit staff add-skill', 'assign' ou 'contract-expertise' pour combler ces manques.[/italic dim]")


@app.command(name="compliance")
def compliance_cmd(
    engagement: str = typer.Option("nordwave-mcx-2027", "--engagement", "-e", help="Identifiant de l'engagement projet"),
    framework: str = typer.Option("NIS2", "--framework", "-f", help="Référentiel réglementaire cible (NIS2, SecNumCloud, ISO27001, 3GPP)"),
    emit_gaps: bool = typer.Option(False, "--emit-gaps", help="Émettre automatiquement des questions d'élicitation pour les contrôles non satisfaits"),
) -> None:
    """Audite la couverture réglementaire d'un projet face aux exigences d'un référentiel (Top-Down Compliance)."""
    import json
    from pathlib import Path
    from rich.table import Table
    from mcp_server.knowledge.tools import get_compliance_matrix

    console.print(f"[bold blue]🛡️ Évaluation de conformité réglementaire pour '{engagement}' face à '{framework}'...[/bold blue]")
    matrix_res = get_compliance_matrix(engagement=engagement, framework=framework)

    if matrix_res.get("status") != "ok":
        console.print(f"[bold red]❌ Erreur : {matrix_res.get('message', 'Échec audit')}[/bold red]")
        return

    data = matrix_res.get("data", {})

    table = Table(title=f"Matrice de Conformité Réglementaire : {framework} — {engagement}")
    table.add_column("Contrôle", style="cyan")
    table.add_column("Intitulé de l'Exigence", style="white")
    table.add_column("Sévérité", style="magenta")
    table.add_column("Statut Projet", style="bold")
    table.add_column("Assets KB Implémentant", style="green")

    unaddressed = []
    for item in data.get("matrix", []):
        st = item["status"]
        status_styled = "[green]COUVERT[/green]" if st == "covered" else "[red]NON COUVERT[/red]"
        impls = ", ".join(item.get("implementing_kb_assets", [])) or "[dim]Aucun pattern KB[/dim]"
        table.add_row(item["control_id"], item["title"], item["severity"], status_styled, impls)
        if st != "covered":
            unaddressed.append(item)

    console.print(table)
    pct = data.get("coverage_percentage", 0.0)
    console.print(f"\n📊 [bold]Couverture du référentiel {framework} :[/bold] {pct}% ({data.get('covered_controls', 0)}/{data.get('total_controls', 0)} exigences)")

    if unaddressed:
        console.print(f"\n[bold yellow]⚠️ {len(unaddressed)} exigence(s) orpheline(s) détectée(s).[/bold yellow]")
        if emit_gaps:
            console.print("[bold cyan]📢 Émission automatique de questions d'élicitation pour les manques réglementaires...[/bold cyan]")
            q_dir = Path(f"projects/{engagement}/mailbox/questions")
            q_dir.mkdir(parents=True, exist_ok=True)
            for u in unaddressed:
                qid = f"Q-COMPL-{u['control_id']}"
                q_file = q_dir / f"{qid}.json"
                q_payload = {
                    "id": qid,
                    "section": "compliance",
                    "routed_to": "security-officer",
                    "control_id": u["control_id"],
                    "framework": framework,
                    "question": f"Comment le système garantit-il la conformité à l'exigence {u['control_id']} ({u['title']}) ?",
                }
                q_file.write_text(json.dumps(q_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                console.print(f"  • Question d'élicitation générée : [cyan]{qid}[/cyan] ({u['control_id']})")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
