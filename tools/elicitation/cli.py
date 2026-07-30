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
) -> None:
    """Extraire le REX et proposer de nouvelles règles de manque à partir des conflits arbitrés."""
    author, _ = resolve_impersonation(as_user, "sofia", "chief-architect", engagement)
    console.print(f"[bold blue]🌾 REX & Harvest pour l'engagement {engagement} par {author}...[/bold blue]")
    console.print("  - Candidate pattern: MCX service decomposition hold until 2nd engagement.")
    console.print("  - New gap rule candidate: Subject decided at L3 with a dependency on another subject below L3.")



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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
