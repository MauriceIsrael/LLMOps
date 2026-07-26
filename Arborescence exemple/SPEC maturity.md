---
id: TPL-elicitation-proto
title: Gap-driven elicitation — prototype specification
type: template
status: draft
confidence: verified
phase: [BUILD]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-26
related: [TPL-mcp-spec, TPL-authoring, TPL-server-fixes]
---

# Gap-driven elicitation — prototype specification

Work order for a coding agent. Build a prototype of the inverted-chatbot model:
the system knows what a project document must contain, detects what is missing,
asks the right expert a precisely framed question, turns the answer into typed
statements after explicit confirmation, checks that the new statements do not
contradict the rest, and renders the document from the accumulated state.

Target stack: Python, LangGraph for the flows, Kùzu for the domain state, the
existing LLMOps MCP server for knowledge base access.

Read `TPL-mcp-spec`, `TPL-authoring` and the principles P-002, P-010, P-012 and
P-013 before starting. They are not background reading: several requirements
below exist only because of them.

---

## 1. What success looks like

A single scripted scenario runs end to end:

1. `elicit scan` finds that section 5.2 of engagement `demo-2026` has no
   statement about the management cluster storage, and that a blocking vendor
   question is unanswered. It writes two `Question` nodes and posts them to the
   mailbox.
2. `elicit answer Q-0001 "..."` submits an expert answer. The flow proposes two
   typed statements, **pauses**, and shows them to the expert for confirmation.
3. `elicit confirm Q-0001 --accept` resumes the paused flow hours later, in a
   new process. The statements are persisted with author and confidence.
4. `elicit answer Q-0002 "..."` submits a contradicting answer from another
   expert. The coherence check detects the contradiction and creates a conflict
   for the chief architect rather than overwriting anything.
5. `elicit assemble` renders section 5.2 from the statements, reports the open
   conflict, and refuses to mark the document complete while it stands.

Step 3 resuming in a **new process** is the load-bearing test. If it does not
work, the durability model is wrong and the rest is a demo, not a prototype.

## 2. Non-goals

Do not build: a web interface, authentication, multi-engagement concurrency,
real-time collaboration, diagram parsing, or automatic conflict resolution.
Do not implement the six gap rules — three are specified below and the other
three are deliberately deferred.

---

## 3. Domain model

State lives in Kùzu, not in LangGraph. LangGraph checkpoints hold only run
position and the payload in flight. Duplicating domain data into LangGraph state
is the most likely design error; do not do it.

```cypher
CREATE NODE TABLE Subject(
    name STRING,            -- canonical, drawn from the glossary where possible
    aliases STRING[],
    definition STRING,
    PRIMARY KEY(name));

CREATE NODE TABLE Statement(
    id STRING,
    engagement STRING,
    section STRING,
    predicate STRING,       -- controlled list, see below
    value STRING,
    unit STRING,
    author STRING,
    role STRING,
    confidence STRING,      -- verified | designed | vendor-stated | assumed
    verbatim STRING,        -- the expert's own words, always kept
    created_at STRING,
    status STRING,          -- proposed | active | superseded | withdrawn
    PRIMARY KEY(id));

CREATE NODE TABLE Question(
    id STRING,
    engagement STRING,
    gap_type STRING,
    section STRING,
    question STRING,
    why_it_matters STRING,
    expected_shape STRING,  -- boolean | number | enum | free_text | decision
    vocabulary STRING[],
    blocking STRING[],      -- sections blocked while unanswered
    routed_to STRING,       -- role, not a person
    status STRING,          -- open | sent | answered | confirmed | declined | rerouted
    created_at STRING,
    PRIMARY KEY(id));

CREATE NODE TABLE Conflict(
    id STRING,
    kind STRING,            -- contradiction | principle_violation | stale_basis
    detail STRING,
    status STRING,          -- open | arbitrated
    resolution STRING,
    arbitrated_by STRING,
    PRIMARY KEY(id));

CREATE REL TABLE ABOUT(FROM Statement TO Subject);
CREATE REL TABLE ANSWERS(FROM Statement TO Question);
CREATE REL TABLE BASED_ON(FROM Statement TO Asset);      -- Asset already exists
CREATE REL TABLE TARGETS(FROM Question TO Subject);
CREATE REL TABLE INVOLVES(FROM Conflict TO Statement);
```

`predicate` is a controlled list for the prototype. Start with exactly these and
reject anything else with a clear error: `has_property`, `is_constrained_by`,
`has_value`, `depends_on`, `is_excluded_because`, `has_effort`,
`has_authority_level`. An open predicate vocabulary destroys contradiction
detection, which is the point of the exercise.

---

## 4. Determinism boundary

Non-negotiable. Implement it as a hard separation in the code, not a convention.

| Concern | Implementation | Rationale |
|---|---|---|
| Detecting a gap | Cypher query only | A model asked to find gaps invents some and misses others silently |
| Detecting a contradiction | Cypher query only | Same |
| Detecting a stale basis | Cypher query only | The supersession relation already exists |
| Phrasing a question | LLM | This is writing, and it is what the LLM is good at |
| Selecting vocabulary to show | Cypher, then LLM only to order | The canonical term must come from the graph |
| Proposing statements from an answer | LLM, then human confirmation | Extraction is a proposal, never a commit |
| Residual semantic coherence | LLM, advisory output only | Cannot gate; it produces a review note |
| Resolving a conflict | Human only | P-002 applied to the document itself |

An LLM must never write to Kùzu directly. All writes go through a repository
module with validation.

---

## 5. Flow A — `scan`

Plain LangGraph state graph, no interrupt. Input: engagement id.

Nodes, in order:

1. `load_frame` — via MCP: the section map, the principles active for the
   engagement's phase and domains, the questionnaires. Read-only.
2. `detect_gaps` — three Cypher rules, each returning structured gap records:
   - **G1 empty_section**: a section in the document config with no `Statement`.
   - **G2 unanswered_blocking**: a questionnaire item whose answer is null and
     whose `blocking_sections` intersects the document config.
   - **G3 principle_unaddressed**: a principle whose domain matches a section's
     domain, where no statement in that section has `BASED_ON` that principle.
3. `enrich` — for each gap, gather from the graph: the canonical `Subject` and
   its aliases, the constraining assets, and **prior answers** — statements with
   the same subject and predicate from other engagements.
4. `crystallize` — one LLM call per gap. Produces `question`, `why_it_matters`,
   `expected_shape`, and a proposed `routed_to` role. The prompt must receive
   the vocabulary and prior answers and must be instructed to present a prior
   answer as a default to confirm or diverge from, not as an open question.
5. `persist_questions` — write `Question` nodes and `TARGETS` relations.
6. `dispatch` — post through the mailbox interface, set status to `sent`.

### 5.1 Semantic refinement — subject maturity

Supersedes the global wave model of an earlier draft, which imposed one cadence
on the whole engagement. Subjects do not mature at the same rate: one may be at
parameter level while another has barely been named. Refinement is therefore
per subject.

Add to the `Subject` node a `level` property, advanced only by the repository
module and never by a model.

| Level | The question at this level asks | Advances when | What the base contributes |
|---|---|---|---|
| `L0` named | nothing — the term exists, no more | a statement mentions it | the canonical term from the glossary |
| `L1` framed | what it is for, its boundary, what must hold | the problem is stated, not the solution | the principles that constrain it |
| `L2` decomposed | what parts it breaks into | each part exists as a subject | **candidate patterns are proposed** |
| `L3` decided | which mechanism for each part | one decision per part, alternatives recorded | prior decisions and their consequences |
| `L4` specified | which values and thresholds | parameters are recorded | values from previous engagements |

**Level-appropriate questions.** The crystallisation step selects the question
template from the subject's current level. A gap that would produce a question
above the subject's level is held, not dispatched — it is not premature because
the subject is missing, but because the subject is not yet ripe. This replaces
the earlier prerequisite rule and subsumes it.

**Pattern proposal at L2.** When a subject reaches `L2`, query the base for
patterns whose problem statement matches the decomposition, and present them in
the next question as candidate solution shapes to confirm or discard — with the
pattern's own "when not to use this" section included. This is where problem and
solution refine together, and it is the point at which the base stops being an
archive and starts being useful. Patterns are proposed, never applied.

**Advancement is a human act.** A level advances when the repository module
records the statements that satisfy the transition, following a confirmation. No
model may set `level`.

### 5.1.1 The maturity board

One command and one rendered artefact answering: what is left to instruct?

```
elicit subjects --engagement demo-2026
```

Columns: subject, level reached, what blocks the next level (open question
reference and the person who owes an answer), how long it has been at this
level, and the document sections that depend on it.

Two derived rules make the board operational rather than decorative:

- **Section readiness.** A section renders as final only when every subject it
  depends on is at `L3` or beyond. Below that it renders provisional, naming the
  subjects that are not ripe. This connects maturity to the document status
  already specified in flow C.
- **Stall detection.** A subject at the same level beyond a configurable
  threshold (default 7 days) with an open question is flagged. In a weekly
  review the useful column is not the levels but who owes an answer and since
  when.

The board is also posted to the mailbox as a single pinned item, updated in
place using the idempotency marker of the mailbox specification, so that
contributors see the whole picture without running anything.

### 5.2 Context carried by every question

A well-crystallised question is narrow, and a narrow question asked without
context cannot be answered. Every `Question` therefore carries two permanent
references, rendered as links:

- `draft_ref` — the section of the current draft, at a stable path with a
  heading anchor;
- `subject_ref` — everything already recorded about the targeted subject:
  active statements, their authors, and any superseded ones with their reason.

`subject_ref` is usually the more useful of the two. Both must be non-stale,
which is why `assemble` renders per section and is triggered after every
confirmation rather than only on demand. Re-rendering one section costs a
fraction of a document.

## 6. Flow B — `intake`

This is where LangGraph earns its place. Input: question id, answer text,
author, role.

Nodes:

1. `load_question` — fetch the question and its frame from Kùzu.
2. `interpret` — one LLM call producing candidate statements: subject,
   predicate, value, unit, confidence. Constraints on the prompt: the subject
   must be an existing `Subject` name or an explicit request to create one; the
   predicate must be in the controlled list; the verbatim answer is carried
   through unchanged. If the answer is a reroute or a refusal, emit no
   statements and set the question status accordingly.
3. **`confirm` — an `interrupt`.** Present the candidate statements to the
   author and stop. The flow resumes with either an acceptance, a corrected set,
   or a rejection.
4. `persist` — write statements with status `active`, link `ANSWERS`, `ABOUT`
   and `BASED_ON`, set the question to `confirmed`.
5. `check` — run the deterministic checks over the newly written statements
   only, not the whole graph:
   - contradiction: same subject and predicate, different value, both active;
   - stale basis: `BASED_ON` an asset whose status is superseded;
   - principle violation: match the statement pattern against the verification
     clause of constraining principles.
   Then one advisory LLM pass for the semantic residue, whose output is stored
   as a note and never blocks.
6. `raise_conflicts` — create `Conflict` nodes, notify both authors and the
   chief architect through the mailbox. **Do not modify or withdraw either
   statement.** Both remain active and in conflict until arbitration.

Checkpointer: durable, on disk. SQLite is sufficient for the prototype. The
thread id must be the question id so that a resume can be addressed by a
different process, days later, without holding anything in memory. Verify the
interrupt and resume API against the installed LangGraph version — the pattern
matters more than the exact import path.

## 7. Flow C — `assemble`

Input: engagement id. Triggered by the chief architect.

1. `gather` — all active statements grouped by section.
2. `render` — one LLM call per section, producing prose **from the statements**,
   which are supplied as the only factual material. Confidence wording rules of
   `TPL-authoring` apply: an `assumed` statement may not be written as fact.
3. `global_check` — cross-section coherence: open conflicts, sections still
   empty, blocking questions still unanswered, terms used that are absent from
   the glossary.
4. `report` — write the document, the list of open conflicts, and the claims
   register. If any conflict is open, the document is marked `provisional` and
   the reason is printed. Rendering is never blocked — a provisional document
   with its defects stated is more useful than no document.

---

## 8. Interfaces

Three, each behind a small protocol so the implementation can be swapped.

```python
class Mailbox(Protocol):
    def post(self, question: Question) -> str: ...      # returns an external ref
    def notify(self, ref: str, message: str) -> None: ...
    def poll(self) -> list[IncomingAnswer]: ...
```

Provide two implementations: `FileMailbox` writing JSON under
`projects/<engagement>/mailbox/` for the prototype, and a stub
`GitHubIssuesMailbox` with the method signatures and a docstring describing the
mapping — one issue per question, labels for section and domain, answer as a
comment. Do not implement the GitHub one now.

```python
class KnowledgeBase(Protocol):     # already exists as tools/authoring/kb_adapter.py
    def select(self, asset_type, phase=None, domains=None): ...
    def asset(self, asset_id): ...
```

Reuse it. Do not write a second MCP client.

```python
class Renderer(Protocol):
    def render_section(self, section_id, statements) -> str: ...
```

---

## 9. Prompts

Three, each in its own file under `prompts/`, each with an explicit output
schema enforced by a parser. Reject and retry once on schema failure, then fail
loudly rather than accepting a malformed structure.

- `crystallize.md` — gap plus context to a question. Must present prior answers
  as defaults. Must produce exactly one answerable question, not a list.
- `interpret.md` — answer to candidate statements. Must refuse to invent a
  subject that does not exist, and must carry the verbatim through.
- `render_section.md` — statements to prose. Reuse the rules already written in
  `tools/authoring/prompts/pass2_section.md`; do not write a third variant of
  the confidence discipline.

## 10. CLI

```
elicit scan       --engagement demo-2026 [--max-questions 8]
elicit questions  --engagement demo-2026 [--status open]
elicit answer     Q-0001 --author alice --role network-architect --text "..."
elicit confirm    Q-0001 [--accept | --reject | --edit file.yaml]
elicit conflicts  --engagement demo-2026
elicit arbitrate  C-0001 --keep S-0007 --reason "..." --by chief-architect
elicit assemble   --engagement demo-2026
```

`arbitrate` sets the losing statement to `superseded` with a link to the winner
and records the reason. It is the only command that may change an existing
statement's status, and it requires the chief architect role.

---

## 11. Acceptance tests

Automated, runnable with `pytest`, using a seeded Kùzu database and a stub LLM
returning canned structured responses. No test may depend on a live model.

1. `test_scan_detects_empty_section` — G1 fires, one question created.
2. `test_scan_prioritises_by_blocking` — with nine gaps and a cap of eight, the
   dropped one is the least blocking.
3. `test_question_carries_vocabulary` — the generated question contains the
   canonical subject name, not an alias.
4. `test_prior_answer_offered` — a subject answered in another engagement
   produces a question containing that prior value.
5. `test_interrupt_resumes_across_processes` — run intake to the interrupt,
   destroy the process, start a new one, resume, assert the statements persist.
   **This is the critical test.**
6. `test_no_statement_without_confirmation` — reject at the interrupt, assert
   nothing was written.
7. `test_contradiction_creates_conflict` — two conflicting statements, one
   conflict, **both statements still active**.
8. `test_conflict_blocks_completion_not_rendering` — assemble produces a
   document marked provisional and lists the conflict.
9. `test_question_matches_subject_level` — a subject at `L1` receives a framing
   question, never a parameter question.
10. `test_level_gate_holds_premature_question` — a parameter gap on an `L1`
    subject is not dispatched, and is dispatched once the subject reaches `L4`.
11. `test_patterns_proposed_at_l2` — reaching `L2` produces candidate patterns
    including their "when not to use this" section.
12. `test_model_cannot_set_level` — an attempt from a flow node raises.
13. `test_board_flags_stall` — a subject unchanged beyond the threshold with an
    open question is flagged with the owner and the elapsed time.
14. `test_section_readiness` — a section whose subjects are below `L3` renders
    provisional and names them.
15. `test_prior_answer_goes_to_confirmation_batch` — not dispatched as a
    question; appears in the batch.
16. `test_question_carries_fresh_context_links` — after a confirmation, the
    draft reference resolves to a section containing the new statement.
17. `test_llm_cannot_write` — assert the repository module is the only writer;
   an attempted direct write from a flow node raises.

## 12. Explicit prohibitions

- No LLM decides that a gap does not exist, that a conflict is resolved, or that
  a statement supersedes another.
- No statement is persisted without passing through the interrupt.
- No domain data is stored in LangGraph state.
- No predicate outside the controlled list.
- No model advances a subject level, and no pattern is applied automatically —
  it is proposed, and a human accepts or discards it.
- No silent overwrite: a contradicting answer never replaces an existing
  statement.
- The verbatim answer is never discarded, even when the extraction is corrected.

## 13. Deliverables

Working code under `tools/elicitation/`, the three prompt files, the Kùzu
migration, the nine tests passing, a `README.md` with the scripted scenario of
section 1 reproduced as copy-pasteable commands, and a short note listing what
was hard and what you would change. That note is the input to the harvest, and
it is part of the deliverable, not an afterthought.
