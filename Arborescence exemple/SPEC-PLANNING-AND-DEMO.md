---
id: TPL-planning-and-demo
title: Instruction planning, dispatch strategy and card-based exchange — specification supplement
type: template
status: draft
confidence: verified
phase: [BUILD]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-27
related: [TPL-elicitation-proto, TPL-mailbox-rendering, TPL-scenario-mcx]
---

# Instruction planning, dispatch strategy and card-based exchange

Complements `TPL-elicitation-proto`. Written from five observations on the first
real run of the Nordwave scenario. Four are defects; the fifth is a conceptual
separation that was implicit and must become visible.

---

## 1. Why twenty-nine gaps produced three questions, and always the same three

### 1.1 What actually happened

The cap never applied. Of 29 gaps, 26 were **held by the level gate** because
they ask L2, L3 or L4 questions of subjects still at `L0_named`. The remaining 3
were dispatched — every dispatchable gap was dispatched. The batch limit of 8 was
never reached.

So the behaviour is correct and the **reporting is wrong**. A run that says
"dispatched 3, held 26" invites the reader to conclude the system is stuck, when
in fact it is refusing to ask premature questions. The report must distinguish
three populations that are currently collapsed into two:

| Population | Meaning | Report as |
|---|---|---|
| open | already dispatched, awaiting an answer | `open` — not a new question |
| newly dispatched | crystallised on this run | `new` |
| held by the gate | the subject is not ripe for this question | `held (premature)` with the level required |
| held by the cap | dispatchable, but over the batch limit | `held (queued)` with the position |

`held (queued)` and `held (premature)` are entirely different situations and
must never share a label. The first says "later, when there is room"; the second
says "later, when we know more".

### 1.2 The same three questions on every scan

Two possible causes, distinguishable in one query:

```cypher
MATCH (q:Question {engagement: $e}) RETURN q.id, q.status, q.created_at ORDER BY q.created_at;
```

- If new `Question` nodes appear on each scan with new identifiers, the scan is
  **re-crystallising** gaps it has already asked. That is a defect: it duplicates
  work, spams the mailbox and breaks idempotency.
- If the same three nodes persist and are merely re-reported, the behaviour is
  right and only the wording is wrong.

**Required.** Scanning is an upsert. A gap whose question is already `open` or
`sent` produces no new question; it refreshes the existing one if its context
changed (a prior answer appeared, the blocking set moved) and reports it as
`open`. The run summary must read:

```
new 0 · open 3 · held-premature 26 · held-queued 0
```

which tells the reader immediately that nothing is stuck and nothing is lost.

---

## 2. Dispatch strategy: why not the next N

The instinct behind the question is sound. The current behaviour is implicitly
**depth-first per subject**: a subject advances, its next question opens, and the
engagement progresses one subject at a time. That is the right shape for a build
phase, where one domain must be nailed down. It is the wrong shape for a bid,
where every section needs something in it before any section needs everything.

Make the choice explicit rather than emergent.

```
elicit scan --engagement X --strategy breadth   # default for BID
elicit scan --engagement X --strategy depth     # default for BUILD
```

**Breadth.** Dispatch the lowest open level across *all* subjects before opening
any higher level. Every subject reaches `L1_framed` before any reaches `L2`.
Produces a document where every section has material early, and a shallow one.

**Depth.** Take a subject as far as it can go before moving on. Produces sections
that are finished and sections that are empty.

Neither is correct in general, which is why it is a parameter. The strategy is
recorded on the engagement so the report can state which one is in force.

### 2.1 The cap is per role, not global

A global cap of 8 across five experts is one or two questions each, and the
engagement crawls. A cap of 8 **per role** is a working queue for each person and
lets five experts progress in parallel — which is the entire point of a
multi-contributor system.

```yaml
dispatch:
  strategy: breadth
  max_open_per_role: 6        # was a single global limit
  max_new_per_scan: 12        # protects against a burst after a decomposition
```

Sort within a role by number of blocked sections descending, then by age.

### 2.2 A decomposition must open the next wave immediately

The first run reported one released gap after a decomposition that created four
subjects. Expected: four new framing questions, one per created subject, subject
to the per-role cap. Verify that subject creation triggers gap re-evaluation
rather than waiting for the next manual scan; if the four subjects produced no
framing gaps, the blueprint does not declare them as required by any section,
which is the subject of section 4.

---

## 3. The instruction plan

Missing today, and it is what a kickoff meeting needs: not the three questions
being asked now, but everything that must eventually be instructed, and by whom.

```
elicit plan --engagement nordwave-mcx-2027 [--format md|table]
```

Produces four blocks.

**Coverage of the blueprint.** For each section of the document being produced:
the subjects it requires, the maturity it requires to render final, where those
subjects stand today, and the resulting section status. This is the answer to
"how far are we from a deliverable".

**The full gap inventory.** All gaps, dispatchable or not, grouped by subject,
with their level and what holds them. Not the three currently asked — all of
them. A reader must be able to see the shape of the whole task on one screen.

**Expertise profiles required.** Derived from the routing of every gap, not only
the dispatched ones:

```
role                      gaps   open   est. answers   contributors
mcx-service-architect       14      3             14   amina
mobile-core-architect       11      2             11   rui
security-architect           4      0              4   — NOT STAFFED
chief-architect              —      —              3   sofia  (arbitration only)
```

A role with gaps and no contributor in the roster is the single most useful
output of this command: it is a staffing gap discovered at kickoff rather than
three weeks in. Print it as a warning.

**The projected sequence.** Given the strategy and the caps, which subjects open
next and what unlocks them. Not a schedule — a dependency order, so that the
chief architect can see that nothing can proceed on section 5.3 until the core is
framed.

---

## 4. Three planes, and why they must be visible

The most important observation of the five. Three kinds of content currently sit
in one database and are indistinguishable in the report, which makes the system
look like a black box that invents subjects.

| Plane | Holds | Lifecycle | Who writes |
|---|---|---|---|
| **Knowledge** | principles, decisions, patterns, questionnaires, effort models, risks | read-only during an engagement | promotion at harvest, by pull request |
| **Blueprint** | the document structure being produced: sections, what each must answer, which subjects it requires, the maturity it needs | versioned, changes rarely, shared across engagements | architecture community |
| **Engagement** | brief, subjects, statements, questions, conflicts, the document | written continuously | contributors |

### 4.1 The blueprint is what generates gaps

This is the clarification that resolves the confusion. **Gaps do not come from
the knowledge base.** They come from the blueprint: the blueprint says a section
must answer something and requires certain subjects at a certain maturity, and a
gap is the distance between that requirement and the engagement's current state.
The knowledge base contributes the *content* of a question — the constraining
principles, the prior answers, the candidate patterns — never its *existence*.

Stated as a rule: **the blueprint asks, the knowledge base informs, the
engagement answers.**

This also explains the `subscriber-db` anomaly in the first run: a subject was
named in a held gap and never appeared in any board. If the blueprint declares
`subscriber-db` as required by a section, the subject must be created at
`L0_named` as soon as the blueprint is bound to the engagement — otherwise the
gap detector is referring to something that does not exist, and the decomposition
in Act 3 appears to create subjects the system already knew about.

**Required.** Binding a blueprint to an engagement creates, at `L0_named`, every
subject the blueprint declares. Decomposition then creates the subjects the
blueprint does *not* declare — the ones an expert discovers — and the report must
distinguish the two:

```
subjects declared by the blueprint     6   (created at binding)
subjects discovered by decomposition   4   (created by an answer)
```

That distinction is what makes the generative property of refinement visible and
credible.

### 4.2 The blueprint must be structured, not prose

Today the section map is a Markdown asset. Since it drives gap detection it needs
a schema.

```yaml
id: BLU-hla-mcx
title: High-level architecture blueprint — mission-critical mobile
type: blueprint
status: active
sections:
  - id: "4.1"
    title: Group and affiliation management
    must_answer: >-
      How are talkgroups modelled, provisioned and affiliated, and what happens
      to affiliation when a site is isolated?
    requires_subjects: [group-management, subscriber-db]
    min_level_final: L3_decided
    min_level_provisional: L1_framed
    informed_by: [principle, decision, pattern]
    routes_to: mcx-service-architect
  - id: "5.3"
    title: Priority, QoS and pre-emption
    must_answer: >-
      Which ARP and 5QI mapping per talkgroup class, and how is pre-emption
      committed end to end?
    requires_subjects: [mobile-core, floor-control]
    min_level_final: L4_specified
    routes_to: mobile-core-architect
```

`min_level_final` per section is what makes section readiness meaningful. In the
first run, section 4.3 rendered provisional although `floor-control` was at
`L3_decided` — either 4.3 requires another subject still green, which the report
must name, or the per-section rule is not wired and a global rule is applying.
With this schema the answer is visible in the plan output.

### 4.3 Provenance in every report

Every table in the progression report gains a provenance marker, so a viewer can
tell at a glance what came from where:

- `⬢ blueprint` — this section, this requirement, this subject existed before the
  engagement started
- `◆ knowledge` — this principle, pattern or prior answer comes from the base
- `● engagement` — this statement, conflict or subject was produced here

A demo where the audience cannot tell which is which will be read as the system
making things up.

---

## 5. Card-based exchange for demonstrations

The command-line answer string is the weakest part of the demonstration: it hides
the card, which is where the design lives.

### 5.1 The file mailbox as a fillable form

`FileMailbox` writes one file per open question under
`artifacts/<engagement>/mailbox/`:

```
mailbox/
  Q-0001.md          the card, plus an answer section to fill in
  Q-0002.md
  answered/          moved here once processed, with the answer preserved
```

The file is the card of `TPL-mailbox-rendering`, followed by:

```markdown
---
## Your answer

<!-- Write below this line, in your own words. Prose is fine and preferred.
     Nothing is recorded until you have seen and confirmed the extraction. -->


## How to submit

    elicit answer --from-file mailbox/Q-0001.md --as amina
```

`elicit answer --from-file` reads the answer section, ignores the card, and runs
the intake flow. The presenter can open the file on screen, type an answer live,
and submit — which shows the card, the human act and the extraction in sequence.

### 5.2 The confirmation, also as a file

The proposal is written to `mailbox/Q-0001.proposal.md`: the candidate
statements as an editable YAML block, the verbatim below, and the three commands.
Editing the block and running `elicit confirm --from-file` resumes the flow with
the corrected set. This makes the "model proposes, human commits" moment
tangible, which no console output does.

### 5.3 Pre-filled answers for a live demonstration

Ship three prepared answers under `demo/answers/` so a presenter can either type
live or submit a prepared one without breaking the flow. They must go through the
same intake path as a typed answer — a demonstration mode that bypasses the flow
proves nothing.

```
demo/answers/amina-framing.md
demo/answers/amina-decomposition.md
demo/answers/rui-contest.md
```

---

## 6. Consequences for the demonstration script

Reordered so that the three planes are visible before anything is generated, and
so that the audience sees a card before it sees a result.

1. **Show the blueprint.** `elicit blueprint --show BLU-hla-mcx`. This is the
   document we are trying to produce, and the source of every question. Thirty
   seconds, and it removes the "where do the questions come from" objection
   before it is raised.
2. **Show the knowledge base.** Through the MCP inspector: principles, a decision
   trail. Generic, reusable, unchanged by this engagement.
3. **Show the brief.** Thin, engagement-specific, filled by one architect.
4. **Bind and plan.** `elicit plan` — the whole task on one screen: coverage,
   the full gap inventory, the expertise profiles, and the staffing warning.
   This is the moment that answers "how big is this".
5. **Scan.** Explain the two kinds of holding. Show that the cap did not bite and
   that the gate did.
6. **Open a card.** Read it aloud: the question, why it matters, the vocabulary,
   the prior answer offered as a default. This is the artefact the whole system
   exists to produce.
7. **Answer and confirm.** Live if possible, showing the proposal before it is
   recorded.
8. **Decompose**, and show four subjects appearing, marked as discovered rather
   than declared.
9. **Declared and detected conflicts**, in that order.
10. **Arbitrate**, then assemble, and read the reason the document is
    provisional.
11. **Query the graph** for the conflicts, to close on the traceability.

Two things to say out loud, because an informed audience will think them: the
reference scenario was written before it ran and its divergences were recorded in
advance; and the run ends provisional on purpose, because the engagement is not
finished and a system that claimed otherwise would be lying.

---

## 7. Acceptance tests

1. `test_scan_is_idempotent` — two consecutive scans with no answer in between
   produce zero new questions and report three open.
2. `test_held_reasons_are_distinguished` — premature and queued are reported
   separately, never under one label.
3. `test_cap_is_per_role` — with two roles and a cap of two, four questions are
   dispatched, not two.
4. `test_breadth_strategy` — no subject reaches L2 while another is at L0.
5. `test_depth_strategy` — one subject reaches L3 while others remain at L0.
6. `test_blueprint_binding_creates_declared_subjects` — binding creates every
   declared subject at `L0_named`; none is referenced by a gap without existing.
7. `test_decomposition_marks_subjects_as_discovered` — subjects created by an
   answer carry a different origin from those declared by the blueprint.
8. `test_plan_reports_unstaffed_role` — a role with gaps and no contributor in
   the roster produces a warning.
9. `test_section_readiness_uses_blueprint_levels` — a section whose blueprint
   requires `L4_specified` stays provisional at `L3_decided`, and the plan names
   the subject responsible.
10. `test_answer_from_file_uses_the_same_path` — a file-submitted answer produces
    the same statements as the same text passed inline.

## 8. Prohibitions

- No gap may reference a subject that does not exist.
- `held (premature)` and `held (queued)` are never merged in any output.
- The demonstration mode must not bypass the intake flow.
- A scan must never create a second question for a gap that already has an open
  one.
