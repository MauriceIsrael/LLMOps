"""
Nordwave MCX acceptance suite — version 2.

Covers what version 1 did not, and what the corrections of `TPL-fixes-scan`,
`TPL-planning-and-demo` and `TPL-refinement-and-contributions` introduced:

  * gaps computed from a blueprint rather than enumerated in the source;
  * counts that reconcile, and holds that carry a reason;
  * an idempotent scan, a per-role cap, and an explicit breadth strategy;
  * three planes made visible: blueprint, knowledge, engagement;
  * question specificity governed by a per-level contract;
  * a subject trajectory showing coarse-to-fine refinement;
  * demotion, because refinement is not monotonic;
  * unsolicited external contribution with two distinct confirmations;
  * declared and detected conflicts, kept separate.

Same two purposes as version 1: it verifies, and it produces the deliverables.
Same rule as version 1: no repository call may substitute for the behaviour under
test.

    pytest tools/elicitation/test_scenario_nordwave_mcx_v2.py -v
    open artifacts/nordwave-mcx-2027/progression.md
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from tools.elicitation.blueprint import bind_blueprint, load_blueprint
from tools.elicitation.flows.assemble import build_assemble_graph
from tools.elicitation.flows.contribution import build_contribution_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.plan import build_plan_graph
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.repository import ElicitationRepository

try:
    from tools.elicitation.flows.harvest import build_harvest_graph
except ImportError:  # pragma: no cover
    build_harvest_graph = None

from langgraph.types import Command

pytestmark = pytest.mark.stochastic


ENGAGEMENT = "nordwave-mcx-2027"
BLUEPRINT_ID = "BLU-hla-mcx"
ARTIFACTS = Path("artifacts") / ENGAGEMENT
DB_PATH = ARTIFACTS / "graph"
BLUEPRINT_PATH = ARTIFACTS / "blueprints" / f"{BLUEPRINT_ID}.yaml"
MAILBOX = ARTIFACTS / "mailbox"

# --------------------------------------------------------------------------
# The blueprint is a fixture file, not a literal in the source. Test 02 mutates
# it, which is the only way to prove that gaps are computed rather than listed.
#
# It is a REDUCED fixture. It echoes the shape of a high-level architecture
# blueprint but is not the real one: a test must not depend on a forty-section
# deliverable. `test_18` checks separately that the real blueprint loads.
#
# Section numbers appear ONCE, here. Everything below refers to sections through
# SECTION[...] or, better, by what they mean — see `gap_for()`. Subjects are
# named directly because a subject is canonical vocabulary; a section number is
# pagination, and no assertion should depend on it.
# --------------------------------------------------------------------------

SECTION = {
    "mcx_framing":        "4.1",
    "mcx_decomposition":  "4.2",
    "floor_arbitration":  "4.3",
    "floor_latency":      "4.3.1",
    "media_topology":     "4.4",
    "lmr_gateway":        "4.5",
    "group_management":   "4.6",
    "core_framing":       "5.1",
    "core_qos":           "5.3",
    "transport":          "5.4",
}
SEC = SECTION.get  # readable alias: SEC("mcx_decomposition")
SYNTHETIC_SECTION = "test-only-synthetic"   # not a number: it is not a chapter

BLUEPRINT = {
    "id": BLUEPRINT_ID,
    "title": "High-level architecture blueprint — mission-critical mobile",
    "version": 1,
    "sections": [
        {"id": SECTION["mcx_framing"], "title": "MCX services boundary and framing",
         "must_answer": "What is the mission-critical service layer for, and what must "
                        "keep working when everything else degrades?",
         "requires": [{"subject": "mcx-services", "level": "L1_framed"}],
         "unlocks": [SECTION[k] for k in ("mcx_decomposition", "floor_arbitration",
                                          "media_topology", "lmr_gateway", "group_management")],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["mcx_decomposition"], "title": "MCX services decomposition",
         "must_answer": "What parts does the service layer break into?",
         "requires": [{"subject": "mcx-services", "level": "L2_decomposed"}],
         "unlocks": [SECTION[k] for k in ("floor_arbitration", "media_topology",
                                          "lmr_gateway", "group_management")],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["floor_arbitration"], "title": "Floor control arbitration",
         "must_answer": "Where does floor arbitration terminate, and what was ruled out?",
         "requires": [{"subject": "floor-control", "level": "L3_decided"}],
         "unlocks": [SECTION["floor_latency"]],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["floor_latency"], "title": "Floor grant latency budget",
         "must_answer": "What latency budget, at which percentile and under what load?",
         "requires": [{"subject": "floor-control", "level": "L4_specified"}],
         "unlocks": [],
         "routes_to": "mobile-core-architect"},
        {"id": SECTION["media_topology"], "title": "Media distribution topology",
         "must_answer": "Unicast or multicast on the radio side, and why?",
         "requires": [{"subject": "media-distribution", "level": "L3_decided"}],
         "unlocks": [],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["lmr_gateway"], "title": "LMR interworking gateway",
         "must_answer": "How does the service layer interwork with the legacy fleet?",
         "requires": [{"subject": "lmr-interworking", "level": "L3_decided"}],
         "unlocks": [],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["group_management"], "title": "Group management and affiliation",
         "must_answer": "How are talkgroups modelled and affiliated?",
         "requires": [{"subject": "group-management", "level": "L3_decided"}],
         "unlocks": [],
         "routes_to": "mcx-service-architect"},
        {"id": SECTION["core_framing"], "title": "Mobile core framing",
         "must_answer": "What is the core for, and what must survive site isolation?",
         "requires": [{"subject": "mobile-core", "level": "L1_framed"}],
         "unlocks": [SECTION["core_qos"]],
         "routes_to": "mobile-core-architect"},
        {"id": SECTION["core_qos"], "title": "Priority, QoS and pre-emption",
         "must_answer": "Which mapping per talkgroup class, committed end to end?",
         "requires": [{"subject": "mobile-core", "level": "L4_specified"},
                      {"subject": "floor-control", "level": "L3_decided"}],
         "unlocks": [],
         "routes_to": "mobile-core-architect"},
        {"id": SECTION["transport"], "title": "Transport topology and redundancy",
         "must_answer": "What redundancy, and what happens on a site cut?",
         "requires": [{"subject": "transport", "level": "L1_framed"}],
         "unlocks": [],
         "routes_to": "security-architect"},   # deliberately unstaffed — see test 01
    ],
}

ANSWER_FRAMING = """
The MCX layer delivers group voice, data and video to dispatchers and field
teams, and it has to keep delivering group voice when almost nothing else works.
Our boundary is the 3GPP MC service layer: group and affiliation management,
floor control, media distribution, and the interworking function towards the
legacy LMR fleet, which stays for four more years. Everything below - bearers,
QoS, slices - belongs to the core team.

What must survive is talkgroup communication inside an isolated site: if the
transport to the national data centres is cut, a site must keep serving its
local talkgroups. That is a hard requirement from the customer, and I do not yet
know whether the platform we shortlist can do it without a local instance.
""".strip()

ANSWER_DECOMPOSITION = """
Four parts. Group and affiliation management, which is mostly a data problem and
talks to the subscriber database. Floor control, which is the latency-critical
one and the reason people will judge the system. Media distribution, where the
question is unicast versus multicast on the radio side. And the LMR interworking
function, which is a gateway to a vendor system we do not control.
""".strip()

CONTRIBUTION_MATERIAL = """
On release 23.4 the element manager's bulk configuration export is capped at
2 000 managed objects per request and rejects concurrent exports on the same
node. In practice a full export of a core node takes three passes. Anyone
planning a nightly backup of the whole estate through that interface should size
for that, and should not assume the documented figure of 10 000.
""".strip()


# ---------------------------------------------------------------- utilities
def api(obj, name: str, criterion: str):
    fn = getattr(obj, name, None)
    if fn is None:
        pytest.fail(f"NOT IMPLEMENTED: {type(obj).__name__}.{name}() is required by: {criterion}")
    return fn


class Report:
    PLANE = {"blueprint": "\u2b22", "knowledge": "\u25c6", "engagement": "\u25cf"}

    def __init__(self, path: Path):
        self.path = path
        self.parts = [
            f"# Progression report — {ENGAGEMENT}\n",
            "_Generated by the acceptance suite from the engagement graph. "
            "Provenance is marked: \u2b22 blueprint (existed before the engagement), "
            "\u25c6 knowledge base (reusable), \u25cf engagement (produced here)._\n",
        ]

    def act(self, title): self.parts.append(f"\n---\n\n## {title}\n")

    def note(self, text): self.parts.append(textwrap.dedent(text).strip() + "\n")

    def table(self, headers, rows):
        self.parts.append("| " + " | ".join(headers) + " |")
        self.parts.append("|" + "|".join(["---"] * len(headers)) + "|")
        for r in rows:
            self.parts.append("| " + " | ".join(str(c) for c in r) + " |")
        self.parts.append("")

    def mermaid(self, body): self.parts.append("```mermaid\n" + textwrap.dedent(body).strip() + "\n```\n")

    def board(self, repo, caption):
        rows = api(repo, "get_subjects_maturity_board", "the board is the overview")(engagement=ENGAGEMENT)
        levels = ["L0_named", "L1_framed", "L2_decomposed", "L3_decided", "L4_specified"]
        out = []
        for row in rows:
            reached = levels.index(row.get("level", "L0_named"))
            cells = " ".join("\u2588" if i <= reached else "\u00b7" for i in range(len(levels)))
            mark = self.PLANE["blueprint"] if row.get("origin") == "blueprint" else self.PLANE["engagement"]
            out.append([f"{mark} {row['subject']}", cells, row.get("level", ""),
                        row.get("origin", "?"), row.get("blocked_by", "\u2014")])
        self.note(f"**{caption}**")
        self.table(["Subject", "L0 L1 L2 L3 L4", "Level", "Origin", "Blocked by"], out)

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.parts), encoding="utf-8")


@pytest.fixture(scope="module")
def report():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    r = Report(ARTIFACTS / "progression.md")
    yield r
    r.write()
    print(f"\nProgression report: {r.path}")


@pytest.fixture(scope="module")
def workspace():
    if ARTIFACTS.exists():
        shutil.rmtree(ARTIFACTS)
    (ARTIFACTS / "blueprints").mkdir(parents=True)
    BLUEPRINT_PATH.write_text(yaml.safe_dump(BLUEPRINT, sort_keys=False), encoding="utf-8")
    return ARTIFACTS


@pytest.fixture(scope="module")
def state():
    return {"done": set()}


@pytest.fixture()
def repo(workspace):
    r = ElicitationRepository(db_path=DB_PATH)
    yield r
    r.close()


def requires(state, act):
    if act not in state["done"]:
        pytest.skip(f"depends on {act}, which did not complete")


def done(state, act):
    state["done"].add(act)


def gap_for(gaps, *, subject, level=None, status="dispatchable"):
    """Finds a gap by what it means, never by a section number.

    A test that asserts on "4.2" is unreadable and breaks on a renumbering.
    "the gap asking mcx-services to decompose" survives both.
    """
    matches = [g for g in gaps
               if g["subject"] == subject
               and (level is None or g.get("required_level") == level)
               and (status is None or g["status"] == status)]
    if not matches:
        available = sorted({(g["subject"], g.get("required_level"), g["status"]) for g in gaps})
        pytest.fail(f"no {status} gap requiring {subject} at {level}. Available: {available}")
    return matches[0]


def scan(strategy="breadth", **over):
    args = {"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "blueprint_id": BLUEPRINT_ID,
            "blueprint_path": str(BLUEPRINT_PATH), "strategy": strategy,
            "max_open_per_role": 6, "max_new_per_scan": 12}
    args.update(over)
    return build_scan_graph().invoke(args)


# ====================================================== 00 · the three planes
def test_00_blueprint_binding_creates_declared_subjects(repo, report, state):
    """D2, D6 and the blueprint/engagement separation."""
    report.act("Phase 0 — the three planes")

    bp = load_blueprint(BLUEPRINT_PATH)
    assert bp.id == BLUEPRINT_ID and len(bp.sections) == len(BLUEPRINT["sections"])

    bind_blueprint(repo, engagement=ENGAGEMENT, blueprint=bp)

    board = repo.get_subjects_maturity_board(engagement=ENGAGEMENT)
    declared = {b["subject"] for b in board if b.get("origin") == "blueprint"}
    expected = {r["subject"] for s in BLUEPRINT["sections"] for r in s["requires"] if r.get("level") == "L1_framed"}
    assert declared == expected, (
        f"binding must create every subject the blueprint declares, at L0_named. "
        f"Missing: {expected - declared}"
    )
    assert all(b["level"] == "L0_named" for b in board)
    assert not any(b.get("origin") == "discovered" for b in board), (
        "nothing is discovered before an expert has answered anything"
    )

    report.note(f"""
        The blueprint declares **{len(expected)} subjects**, all created at
        `L0_named` with origin `blueprint`. Nothing is discovered yet: discovery
        is what answers produce.

        This is the separation that makes the rest legible — \u2b22 existed before the
        engagement, \u25cf is produced by it.
    """)
    report.board(repo, "Board after binding")
    done(state, "00")


def test_01_plan_reports_coverage_and_an_unstaffed_role(repo, report, state):
    """The instruction plan, and the staffing gap it must surface."""
    requires(state, "00")
    roster = [{"login": "amina", "roles": ["mcx-service-architect"]},
              {"login": "rui", "roles": ["mobile-core-architect"]},
              {"login": "sofia", "roles": ["chief-architect"]}]
    (ARTIFACTS / "roster.yaml").write_text(yaml.safe_dump(roster), encoding="utf-8")

    plan = build_plan_graph().invoke(
        {"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "blueprint_id": BLUEPRINT_ID,
         "blueprint_path": str(BLUEPRINT_PATH), "roster_path": str(ARTIFACTS / "roster.yaml")})

    coverage = plan.get("coverage", [])
    assert len(coverage) == len(BLUEPRINT["sections"]), "coverage must cover every section"
    assert all(c["status"] in ("final", "provisional", "empty") for c in coverage)

    profiles = plan.get("expertise_profiles", [])
    assert profiles, "the plan must state which expertise the engagement needs"
    unstaffed = [p for p in profiles if p.get("staffed") is False]
    assert any(p["role"] == "security-architect" for p in unstaffed), (
        "one section routes to security-architect and nobody in the roster holds "
        "that role — a staffing gap must be reported at kickoff, not discovered "
        "three weeks in"
    )

    report.note(f"""
        The plan covers **{len(coverage)} sections** and derives the expertise
        needed from the routing of every gap, not only the dispatched ones.
        **{len(unstaffed)} role(s) unstaffed** — reported now rather than found later.
    """)
    report.table(["Role", "Gaps", "Staffed by"],
                 [[p["role"], p.get("gap_count", "?"),
                   ", ".join(p.get("contributors", [])) or "\u26a0 NOT STAFFED"] for p in profiles])
    done(state, "01")


# ====================================================== 02 · detection is computed
def test_02_gaps_are_computed_from_the_blueprint(repo, report, state):
    """The discriminating test. It cannot pass while a hardcoded catalogue exists."""
    requires(state, "00")
    report.act("Phase 1 — gap detection is computed, not enumerated")

    before = {(g["section"], g["subject"]) for g in scan()["gaps"]}

    mutated = json.loads(json.dumps(BLUEPRINT))
    mutated["sections"].append(
        {"id": SYNTHETIC_SECTION, "title": "Synthetic section added by the test",
         "must_answer": "Does the detector read the blueprint?",
         "requires": [{"subject": "synthetic-subject", "level": "L1_framed"}],
         "unlocks": [], "routes_to": "mcx-service-architect"})
    BLUEPRINT_PATH.write_text(yaml.safe_dump(mutated, sort_keys=False), encoding="utf-8")
    try:
        after = {(g["section"], g["subject"]) for g in scan()["gaps"]}
        assert (SYNTHETIC_SECTION, "synthetic-subject") in after, (
            "adding a section to the blueprint produced no gap: detection is not "
            "reading the blueprint, it is enumerating a list in the source"
        )
        assert after - before == {(SYNTHETIC_SECTION, "synthetic-subject")}
    finally:
        BLUEPRINT_PATH.write_text(yaml.safe_dump(BLUEPRINT, sort_keys=False), encoding="utf-8")

    restored = {(g["section"], g["subject"]) for g in scan()["gaps"]}
    assert restored == before, "removing the section must remove its gaps"

    src = Path("tools/elicitation/flows/scan.py").read_text(encoding="utf-8")
    for name in ("mcx-services", "mobile-core", "transport", "floor-control"):
        assert name not in src, (
            f"'{name}' appears in scan.py: subject names belong in the blueprint, "
            f"never in the detector"
        )

    report.note("""
        A section added to the blueprint produced a gap; removing it removed the
        gap; and no subject name appears in the detector's source. Gaps are the
        distance between what the blueprint requires and what the engagement
        holds — nothing is enumerated.
    """)
    done(state, "02")


def test_03_counts_reconcile_and_every_hold_is_explained(repo, report, state):
    """D4: nothing is dropped, and a suppression is never silent."""
    requires(state, "02")
    res = scan()
    gaps, counts = res["gaps"], res["counts_summary"]

    assert counts["total"] == len(gaps)
    assert counts["total"] == sum(v for k, v in counts.items() if k != "total"), (
        f"counts do not reconcile: {counts}. A gap was dropped rather than held."
    )
    for g in gaps:
        if g["status"] not in ("dispatchable", "satisfied"):
            assert g.get("hold_reason"), f"{g['section']} held with no reason"
        assert set(g["blocking"]) <= {s["id"] for s in BLUEPRINT["sections"]}, (
            f"{g['section']} blocks sections that do not exist: {g['blocking']}"
        )

    premature = [g for g in gaps if g["status"] == "held_premature"]
    queued = [g for g in gaps if g["status"] == "held_queued"]
    assert premature, "on a freshly bound blueprint most gaps must be premature"

    report.note(f"""
        **{counts['total']}** gaps evaluated · dispatchable **{counts['dispatchable']}** ·
        held-premature **{counts['held_premature']}** · held-queued **{counts['held_queued']}** ·
        satisfied **{counts['satisfied']}**. The four sum to the total: nothing is
        dropped, and the two kinds of holding are never merged — one says *later,
        when there is room*, the other *later, when we know more*.
    """)
    report.table(["Section", "Subject", "Status", "Reason"],
                 [[g["section"], g["subject"], g["status"], g.get("hold_reason", "\u2014")]
                  for g in (premature[:4] + queued[:2])])
    state["dispatched"] = [g for g in gaps if g["status"] == "dispatchable"]
    done(state, "03")


def test_04_scan_is_idempotent(repo, report, state):
    """A second scan with no answer in between creates nothing new."""
    requires(state, "03")
    first = scan()
    ids_before = {q["id"] for q in first.get("questions", [])}
    second = scan()
    ids_after = {q["id"] for q in second.get("questions", [])}

    assert ids_after == ids_before, "the scan re-crystallised questions it had already asked"
    assert second["counts_summary"].get("new", 0) == 0
    assert second["counts_summary"].get("open", 0) == len(ids_before)

    report.note(f"""
        Second scan: **new 0 · open {len(ids_before)}**. A question already open is
        refreshed, never duplicated — otherwise the mailbox fills with the same
        card and the reader concludes the system is stuck.
    """)
    done(state, "04")


def test_05_cap_is_per_role_and_breadth_is_honoured(repo, report, state):
    """Two roles with a cap of one must yield two questions, not one."""
    requires(state, "04")
    res = scan(max_open_per_role=1, force_refresh=True)
    dispatched = [q for q in res.get("questions", []) if q.get("status") in (None, "open", "new")]
    roles = {q["routes_to"] for q in dispatched}
    assert len(roles) >= 2, (
        "a cap of one per role across several roles must dispatch one question per "
        "role; a global cap would have dispatched one in total"
    )
    per_role = {r: sum(1 for q in dispatched if q["routes_to"] == r) for r in roles}
    assert all(n <= 1 for n in per_role.values()), f"cap exceeded: {per_role}"

    levels = {q.get("level") for q in dispatched}
    assert levels <= {"L1_framing"}, (
        f"breadth strategy must open the lowest level everywhere first, got {levels}"
    )
    report.note(f"""
        With a cap of one per role, **{len(dispatched)} questions** went out across
        **{len(roles)} roles** — a global cap would have sent one. Breadth strategy:
        every dispatched question is a framing question.
    """)
    done(state, "05")


# ====================================================== 06 · refinement visible
def test_06_framing_through_a_card_file(repo, report, state):
    """The extraction, submitted the way an expert actually submits it."""
    requires(state, "03")
    report.act("Phase 2 — refinement, seen through one subject")

    q = next(g for g in state["dispatched"] if g["subject"] == "mcx-services")
    qid = q.get("question_id") or q["id"]

    card = MAILBOX / f"{qid}.md"
    assert card.exists(), (
        "the file mailbox must write a fillable card per open question; the card "
        "is where the design lives and a CLI string hides it"
    )
    body = card.read_text(encoding="utf-8")
    for block in ("Why this matters", "Please use these terms", "Your answer"):
        assert block in body, f"the card is missing the '{block}' block"

    card.write_text(body.replace("## Your answer\n", f"## Your answer\n\n{ANSWER_FRAMING}\n"),
                    encoding="utf-8")

    checkpointer = get_sqlite_checkpointer(engagement=ENGAGEMENT)
    graph = build_intake_graph(checkpointer=checkpointer)
    cfg = {"configurable": {"thread_id": qid}}
    graph.invoke({"question_id": qid, "from_file": str(card), "as_person": "amina",
                  "engagement": ENGAGEMENT, "db_path": str(DB_PATH)}, config=cfg)

    assert not repo.get_active_statements(engagement=ENGAGEMENT), "recorded before confirmation"
    result = graph.invoke(Command(resume={"action": "accept", "accept": True}), config=cfg)
    ids = result.get("persisted_statement_ids", [])
    assert len(ids) >= 2

    get_statement = api(repo, "get_statement", "confidence must be inspectable")
    stmts = [get_statement(i) for i in ids]
    assert len({s["confidence"] for s in stmts}) >= 2, (
        "the answer mixes a design decision with a customer requirement; they "
        "cannot carry the same epistemic status"
    )
    print("DEBUG TEST 06 STMTS VERBATIMS:", [s.get("verbatim") for s in stmts])
    assert any(ANSWER_FRAMING[:60] in s.get("verbatim", "") for s in stmts)
    unc = api(repo, "get_uncertainties", "an admitted unknown must not become a fact")(
        engagement=ENGAGEMENT, subject="mcx-services")
    assert unc and all("do not yet know" not in s["value"].lower() for s in stmts)
    assert repo.get_subject_maturity(engagement=ENGAGEMENT, name="mcx-services")["level"] == "L1_framed"

    report.note(f"""
        Amina answered by editing the card file. **{len(ids)} statements**,
        **{len({s['confidence'] for s in stmts})} confidence levels**, one recorded
        uncertainty, `mcx-services` \u2192 `L1_framed`.
    """)
    report.table(["Id", "Predicate", "Value", "Confidence"],
                 [[s["id"], s["predicate"], s["value"][:64], s["confidence"]] for s in stmts])
    state["qid_framing"] = qid
    done(state, "06")


def test_07_resume_in_a_separate_process(repo, report, state):
    """The load-bearing durability property."""
    requires(state, "06")
    res = scan()
    q = gap_for(res["gaps"], subject="mobile-core", level="L1_framed")
    qid = q.get("question_id") or q["section"]

    graph = build_intake_graph(checkpointer=get_sqlite_checkpointer(engagement=ENGAGEMENT))
    cfg = {"configurable": {"thread_id": qid}}
    graph.invoke({"question_id": qid, "answer_text":
                  "A dedicated 5G standalone core, national, two sites active-active, "
                  "with a slice reserved for the mission-critical service.",
                  "author": "rui", "role": "mobile-core-architect",
                  "engagement": ENGAGEMENT, "db_path": str(DB_PATH)}, config=cfg)
    repo.close()
    from mcp_server.db.kuzu_client import KuzuClient
    KuzuClient.clear_cache(str(DB_PATH))

    script = textwrap.dedent(f"""
        from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
        from langgraph.types import Command
        g = build_intake_graph(checkpointer=get_sqlite_checkpointer(engagement="{ENGAGEMENT}"))
        r = g.invoke(Command(resume={{"action": "accept", "accept": True}}),
                     config={{"configurable": {{"thread_id": "{qid}"}}}})
        print(len(r.get("persisted_statement_ids", [])))
    """)
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"resuming from another process failed; an expert cannot answer three days "
        f"later:\n{proc.stderr[-600:]}"
    )
    report.note("""
        Paused in one process, resumed in another, addressed only by the question
        identifier.
    """)
    done(state, "07")


def test_08_decomposition_creates_discovered_subjects(repo, report, state):
    """Refinement is generative, and the base is honest about what it lacks."""
    requires(state, "06")
    res = scan()
    q = gap_for(res["gaps"], subject="mcx-services", level="L2_decomposed")
    qid = q.get("question_id") or q["section"]

    before = {b["subject"] for b in repo.get_subjects_maturity_board(engagement=ENGAGEMENT)}
    graph = build_intake_graph(checkpointer=get_sqlite_checkpointer(engagement=ENGAGEMENT))
    cfg = {"configurable": {"thread_id": qid}}
    paused = graph.invoke({"question_id": qid, "answer_text": ANSWER_DECOMPOSITION,
                           "author": "amina", "role": "mcx-service-architect",
                           "engagement": ENGAGEMENT, "db_path": str(DB_PATH)}, config=cfg)

    patterns = paused.get("candidate_patterns") or []
    pat = next((p for p in patterns if p.get("id") == "PAT-006"), None)
    assert pat and pat.get("when_not_to_use"), (
        "PAT-006 must be proposed for the interworking part, with its 'when not to "
        "use' section; a pattern proposed without it is advocacy"
    )
    assert paused.get("no_pattern_for_decomposition") is True, (
        "the base holds no pattern for this decomposition and must say so"
    )
    graph.invoke(Command(resume={"action": "accept", "accept": True}), config=cfg)

    board = repo.get_subjects_maturity_board(engagement=ENGAGEMENT)
    discovered = {b["subject"] for b in board if b.get("origin") == "discovered"}
    created = {b["subject"] for b in board} - before
    assert created, "a decomposition must create subjects"
    assert created <= discovered, (
        f"subjects created by an answer must carry origin 'discovered', not "
        f"'blueprint': {created - discovered}"
    )
    assert repo.get_subject_maturity(engagement=ENGAGEMENT, name="mcx-services")["level"] == "L2_decomposed"

    report.note(f"""
        The decomposition created **{len(created)} subjects**, all marked
        `discovered` — distinct from the {len(before)} the blueprint declared. The
        base proposed **PAT-006**, written for another domain, and reported having
        **no pattern** for the decomposition itself: a first occurrence, and a
        promotion candidate.
    """)
    report.mermaid("""
        graph TD
            MCX["\u2b22 mcx-services · L2_decomposed"]
            PAT["\u25c6 PAT-006 (candidate)<br/>when not to use: documented direct access"]
            PAT -. proposed .-> MCX
            MCX --> GM["\u25cf group-management"]
            MCX --> FC["\u25cf floor-control"]
            MCX --> MD["\u25cf media-distribution"]
            MCX --> LMR["\u25cf lmr-interworking"]
    """)
    report.board(repo, "Board after decomposition")
    done(state, "08")


def test_09_question_specificity_respects_its_level(repo, report, state):
    """A question must not be finer than the subject is ripe for."""
    requires(state, "08")
    res = scan()
    forbidden = ("ms", "percentile", "throughput", "gbps", "5qi", "arp")
    for g in res["gaps"]:
        if g["status"] != "dispatchable":
            continue
        text = (g.get("question") or "").lower()
        if g.get("level") in ("L1_framing", "L2_decomposition") and text:
            assert not any(t in text for t in forbidden), (
                f"a {g['level']} question mentions a quantity: {text[:90]!r}. The "
                f"level contract forbids it; the model drifts towards precision "
                f"because precise questions sound competent."
            )
    report.note("""
        Every dispatched framing or decomposition question was checked against its
        level contract: no threshold, unit or technology name. Specificity is
        declared, not left to the model's judgement.
    """)
    done(state, "09")


def test_10_trajectory_shows_increasing_specificity(repo, report, state):
    """The artefact that makes refinement self-evident."""
    requires(state, "08")
    traj = api(repo, "get_subject_trajectory", "refinement must be observable per subject")(
        engagement=ENGAGEMENT, subject="mcx-services")
    assert len(traj) >= 2, "mcx-services advanced two levels; both must appear"
    order = [t["level"] for t in traj]
    assert order == sorted(order, key=lambda lvl: ["L0_named", "L1_framed", "L2_decomposed",
                                                 "L3_decided", "L4_specified"].index(lvl))
    assert all(t.get("question") and t.get("answer_excerpt") for t in traj), (
        "each step must pair the question with what it produced"
    )
    report.note("**Trajectory of `mcx-services`** — coarse to fine, one step per level.")
    report.table(["Level", "Question", "What it produced"],
                 [[t["level"], t["question"][:70], t["answer_excerpt"][:70]] for t in traj])
    done(state, "10")


# ====================================================== 11 · disagreement
def test_11_contest_declares_a_conflict(repo, report, state):
    requires(state, "08")
    report.act("Phase 3 — disagreement, declared and detected")

    s34 = repo.save_statement({
        "engagement": ENGAGEMENT, "section": SECTION["floor_arbitration"], "subject": "floor-control",
        "predicate": "has_property",
        "value": "arbitration terminates in the MC service layer, at the site",
        "author": "amina", "role": "mcx-service-architect",
        "confidence": "designed", "status": "active"})
    repo.advance_subject_level(engagement=ENGAGEMENT, name="floor-control", level="L3_decided")

    s41, cid = repo.contest_statement(
        target_statement_id=s34, author="rui", role="mobile-core-architect",
        engagement=ENGAGEMENT,
        text="depends on a committed priority and pre-emption profile in the core")

    active = {s["id"] for s in repo.get_active_statements(engagement=ENGAGEMENT)}
    assert s34 in active and s41 in active, "a contest raises a disagreement, it does not withdraw"
    conf = api(repo, "get_conflict", "a conflict must be inspectable")(cid)
    assert conf.get("origin") == "declared"

    report.note("""
        Rui was never asked this question. He contested a specific statement, and
        the conflict is marked **declared** — a human asserted it. Both positions
        remain active.
    """)
    state.update({"s34": s34, "s41": s41, "cid": cid})
    done(state, "11")


def test_12_check_node_detects_what_nobody_declared(repo, report, state):
    """The path that proves detection, as opposed to declaration."""
    requires(state, "08")
    common = {"engagement": ENGAGEMENT, "section": SECTION["media_topology"], "subject": "media-distribution",
              "predicate": "has_property", "confidence": "designed", "status": "active"}
    a = repo.save_statement({**common, "value": "multicast on the radio side",
                             "author": "amina", "role": "mcx-service-architect"})
    b = repo.save_statement({**common, "value": "unicast only, multicast deferred",
                             "author": "rui", "role": "mobile-core-architect"})

    found = api(repo, "run_checks", "check_node must detect without a human declaring")(
        engagement=ENGAGEMENT, statement_ids=[b])
    detected = [c for c in found if c.get("kind") == "contradiction"]
    assert detected, (
        "two active statements on the same subject and predicate with different "
        "values must be found by query. If only contest_statement can raise a "
        "conflict, the system declares disagreements but does not find them."
    )
    assert detected[0].get("origin") == "detected"
    active = {s["id"] for s in repo.get_active_statements(engagement=ENGAGEMENT)}
    assert {a, b} <= active

    report.note("""
        Nobody contested: two answers landed independently and the check node
        found the contradiction by query, `origin: detected`. A declared conflict
        proves only that a human can raise one.
    """)
    done(state, "12")


def test_13_arbitration_amends_keeps_and_generates(repo, report, state):
    requires(state, "11")
    amended = "floor arbitration terminates in the MC service layer at the site"
    reason = ("Both are right and the disagreement is one of scope. Arbitration is "
              "local; the end-to-end floor grant is not.")
    repo.arbitrate_conflict(conflict_id=state["cid"], keep_statement_id=state["s41"],
                            reason=reason, arbitrated_by="sofia",
                            amend_statement_id=state["s34"], amend_to=amended)

    get_statement = api(repo, "get_statement", "the amended statement must be inspectable")
    a34 = get_statement(state["s34"])
    assert a34["value"] == amended and a34["status"] == "active"
    assert a34.get("previous_values"), "an amendment is a change, not an erasure"
    assert get_statement(state["s41"])["status"] == "active"
    conf = repo.get_conflict(state["cid"])
    assert conf["status"] == "arbitrated" and reason[:30] in conf["resolution"]

    report.note("""
        Sofia amended one statement and kept the other: the disagreement was one of
        scope. The previous wording is in the history. An arbitration that could
        only pick a winner would have forced her to discard a true statement.
    """)
    done(state, "13")


# ====================================================== 14 · non-monotonic
def test_14_demotion_flags_and_reopens_with_context(repo, report, state):
    """Refinement can go backwards, and must do so without punishing the expert."""
    requires(state, "13")
    report.act("Phase 4 — refinement is not monotonic, and outsiders can contribute")

    demote = api(repo, "demote_subject", "an arbitration can invalidate a framing")
    demote(engagement=ENGAGEMENT, name="floor-control", to_level="L2_decomposed",
           by="sofia", reason="the decomposition missed the interworking case")

    assert repo.get_subject_maturity(engagement=ENGAGEMENT, name="floor-control")["level"] == "L2_decomposed"
    above = [s for s in repo.get_active_statements(engagement=ENGAGEMENT)
             if s["subject"] == "floor-control" and s.get("status") == "under_review"]
    assert above, "statements above the new level must be flagged, not deleted"

    res = scan()
    reopened = [g for g in res["gaps"]
                if g["subject"] == "floor-control" and g["status"] == "dispatchable"]
    assert reopened, "demotion must reopen the questions of the levels given up"
    assert any(g.get("prior_answer") for g in reopened), (
        "a reopened question must carry the previous answer as context; a demotion "
        "must not feel like a punishment for having answered"
    )
    report.note(f"""
        `floor-control` demoted to `L2_decomposed`. **{len(above)} statements** marked
        `under_review` rather than deleted, and **{len(reopened)}** questions reopened
        carrying their previous answers.
    """)
    done(state, "14")


def test_15_external_contribution_needs_two_confirmations(repo, report, state):
    """An outsider offers material; the author confirms meaning, the lead accepts entry."""
    requires(state, "08")
    material = ARTIFACTS / "contributions" / "enm-export-limits.md"
    material.parent.mkdir(parents=True, exist_ok=True)
    material.write_text(CONTRIBUTION_MATERIAL, encoding="utf-8")

    flow = build_contribution_graph()
    sub = flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH),
                       "action": "submit", "as_person": "external:m.okonkwo",
                       "title": "ENM northbound export limits on release 23.4",
                       "material_path": str(material), "relates_to": "lmr-interworking"})
    cid = sub["contribution_id"]

    assert not [s for s in repo.get_active_statements(engagement=ENGAGEMENT)
                if s.get("contribution_id") == cid], "material entered before triage"

    flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "action": "triage",
                 "contribution_id": cid, "as_person": "sofia", "decision": "accept",
                 "to_subject": "lmr-interworking"})
    cry = flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH),
                       "action": "crystallise", "contribution_id": cid})
    proposed = cry.get("proposed_statements", [])
    assert proposed, "crystallisation must propose statements from the material"
    assert cry.get("unmapped_terms") is not None, (
        "the mapping of the contributor's terms onto canonical subjects must be "
        "reported, including what could not be mapped"
    )
    assert not [b for b in repo.get_subjects_maturity_board(engagement=ENGAGEMENT)
                if b.get("origin") == "external"], (
        "an external contribution may propose a subject, never create one"
    )

    # The lead accepting first must not record anything: order matters.
    early = flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "action": "accept",
                         "contribution_id": cid, "as_person": "sofia", "section": SECTION["lmr_gateway"]})
    assert early.get("rejected") or not early.get("persisted_statement_ids"), (
        "the lead cannot accept before the author has confirmed the extraction: only "
        "the author can say whether it represents what they meant"
    )

    flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "action": "confirm",
                 "contribution_id": cid, "as_person": "external:m.okonkwo", "accept": True})
    acc = flow.invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "action": "accept",
                       "contribution_id": cid, "as_person": "sofia", "section": SECTION["lmr_gateway"]})
    ids = acc.get("persisted_statement_ids", [])
    assert ids, "after both confirmations the statements must be recorded"
    st = repo.get_statement(ids[0])
    assert st["author"] == "external:m.okonkwo", "the contributor is credited"
    assert st.get("verbatim"), "their material is retained"

    report.note(f"""
        An architect outside the engagement offered a note on vendor export limits.
        Two distinct confirmations were required: the **author confirmed the
        meaning**, the **lead accepted the entry**. Accepting before the author had
        confirmed was refused. **{len(ids)} statements** recorded, credited to the
        contributor, with their material attached.
    """)
    done(state, "15")


# ====================================================== 16 · the deliverable
def test_16_assembly_is_provisional_for_a_maturity_reason(repo, report, state):
    requires(state, "13")
    report.act("Phase 5 — the deliverable, and why it is honest about being unfinished")

    res = build_assemble_graph().invoke(
        {"engagement": ENGAGEMENT, "db_path": str(DB_PATH), "blueprint_id": BLUEPRINT_ID,
         "blueprint_path": str(BLUEPRINT_PATH)})

    assert res["is_provisional"] is True
    unripe = res.get("unripe_subjects", [])
    assert unripe
    open_conflicts = res.get("open_conflicts")
    assert open_conflicts is not None, "the cause of a provisional status must be attributable"
    sections = res.get("section_status", {})
    assert sections and all(v in ("final", "provisional", "empty") for v in sections.values())

    (ARTIFACTS / "document.md").write_text(res.get("document", ""), encoding="utf-8")

    report.note(f"""
        **PROVISIONAL** with **{open_conflicts}** conflict(s) open and
        **{len(unripe)}** subjects below their required level. The document is held
        back by immaturity, not by disagreement. A run reaching COMPLETE here would
        have failed: this engagement is not finished.
    """)
    report.table(["Section", "Status", "Required"],
                 [[k, v, ", ".join(f"{r['subject']}@{r['level']}"
                                   for s in BLUEPRINT["sections"] if s["id"] == k
                                   for r in s["requires"])] for k, v in sorted(sections.items())])
    report.board(repo, "Board at assembly")
    done(state, "16")


def test_17_harvest_proposes_candidates_including_the_contribution(repo, report, state):
    requires(state, "16")
    report.act("Phase 6 — harvest")
    if build_harvest_graph is None:
        pytest.fail("NOT IMPLEMENTED: flows/harvest.py — without it the base never learns")

    res = build_harvest_graph().invoke({"engagement": ENGAGEMENT, "db_path": str(DB_PATH),
                                        "by": "sofia"})
    candidates = res.get("promotion_candidates", [])
    assert candidates
    if "15" in state["done"]:
        assert any(c.get("source") == "external-contribution" for c in candidates), (
            "an accepted external contribution is general almost by definition and "
            "is a first-class promotion candidate"
        )
    report.table(["Candidate", "Kind", "Source"],
                 [[c.get("title", "?")[:56], c.get("kind", "?"), c.get("source", "\u2014")]
                  for c in candidates])
    (ARTIFACTS / "harvest.json").write_text(json.dumps(res, indent=2, default=str))
    done(state, "17")


# ====================================================== 18 · the real blueprint
def test_18_the_real_blueprint_loads_and_validates(report):
    """The fixture above is reduced. The deliverable's blueprint is checked here.

    Kept separate on purpose: the acceptance suite must not depend on a forty-
    section document, but nobody should be able to break the real blueprint and
    have every test still pass.
    """
    real = Path("blueprints/BLU-hla-mcx.yaml")
    if not real.exists():
        pytest.skip("the real blueprint is not yet in the repository")

    bp = load_blueprint(real)
    assert bp.sections, "the blueprint declares no section"

    ids = [s.id for s in bp.sections]
    assert len(ids) == len(set(ids)), "duplicate section identifiers"

    declared = {r.subject for s in bp.sections for r in s.requires}
    for s in bp.sections:
        for target in s.unlocks:
            assert target in ids, (
                f"section {s.id} unlocks {target}, which is not a section of this "
                f"blueprint — `blocking` would then report an identifier that does "
                f"not exist"
            )
        assert s.must_answer, f"section {s.id} has no question to answer"
        assert s.routes_to, f"section {s.id} routes to nobody"

    report.act("Appendix — the real blueprint")
    report.note(f"""
        `{real}` validates: **{len(ids)} sections**, **{len(declared)} distinct
        subjects**, every `unlocks` target resolves, every section states what it
        must answer and who it routes to.

        The suite above runs on a reduced fixture. This check is what stops the
        real deliverable's structure from drifting unnoticed.
    """)
    report.table(["Section", "Requires", "Unlocks", "Routes to"],
                 [[s.id, ", ".join(f"{r.subject}@{r.level}" for r in s.requires),
                   len(s.unlocks), s.routes_to] for s in bp.sections[:12]])
