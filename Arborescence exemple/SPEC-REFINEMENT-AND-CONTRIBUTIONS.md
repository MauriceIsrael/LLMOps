---
id: TPL-refinement-and-contributions
title: Visible refinement and unsolicited contributions — specification supplement
type: template
status: draft
confidence: verified
phase: [BUILD]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-27
related: [TPL-elicitation-proto, TPL-planning-and-demo, TPL-mailbox-rendering]
---

# Visible refinement and unsolicited contributions

Complements `TPL-elicitation-proto`. Two additions: making the coarse-to-fine
progression observable rather than merely implemented, and opening a second entry
path for material offered by someone the engagement never asked.

---

# Part A — Making refinement visible

The maturity ladder exists and works, but nobody can see it working. A run shows
subjects at levels; it does not show a subject *travelling*, and the travelling
is the idea. Three additions fix that.

## A1. Question specificity is declared, not emergent

Today the crystallisation prompt receives the subject's level and is trusted to
produce a question of appropriate scope. That makes fineness a property of the
model's mood, which is neither reproducible nor auditable. Declare it instead:
each level carries a question template with an explicit scope contract.

```yaml
question_templates:
  L1_framing:
    scope: "the purpose, the boundary, and what must hold"
    forbids: [a mechanism, a technology, a number]
    shape: prose
    example: >-
      What is {subject} for, and what must keep working when everything else
      degrades?
  L2_decomposition:
    scope: "the parts, and nothing about how any part works"
    forbids: [a mechanism for a part, a technology, a number]
    shape: list_of_parts
    example: >-
      What parts does {subject} break into, and which of them carries the risk?
  L3_decision:
    scope: "the mechanism for one named part, and the alternatives rejected"
    forbids: [a threshold, a sizing value]
    requires: [one part named]
    shape: decision_with_alternatives
    example: >-
      For {part}, which mechanism, and what did you rule out?
  L4_specification:
    scope: "a value, its unit, and the condition under which it holds"
    requires: [one decided mechanism named]
    shape: value_with_unit_and_condition
    example: >-
      For {part} under {mechanism}, what is the {parameter}, at which percentile
      and under what load?
```

The `forbids` clause is the operative one. A crystallisation that produces a
question mentioning a threshold while the subject is at `L2` has violated the
contract, and the check is mechanical: reject and retry once, then fail loudly.
Without it, the model will drift towards precision because precise questions
sound more competent, and the whole progression collapses on the first run.

## A2. The subject trajectory

```
elicit subject floor-control --trajectory
```

Renders the chain of questions and the answers that advanced the subject, in
order. This is the artefact that makes the concept self-evident to an audience,
because the progression speaks for itself:

```
floor-control · declared by blueprint · now L4_specified

  L1  "What is floor control for, and what must hold when a site is isolated?"
      → amina, day 3 · the floor is the right to transmit in a talkgroup; it must
        be grantable inside an isolated site
      ⇒ L1_framed

  L2  "What parts does floor control break into, and which carries the risk?"
      → amina, day 5 · arbitration, queueing policy, override for priority users
      ⇒ L2_decomposed · 3 subjects created

  L3  "For arbitration, which mechanism, and what did you rule out?"
      → amina, day 8 · terminates in the MC service layer at the site; rejected
        a central arbiter because it fails under site isolation
      ⇒ L3_decided · contested day 12 by rui, arbitrated day 14 by sofia

  L4  "For arbitration under local termination, what is the floor grant latency
       budget, at which percentile and under what load?"
      → rui, day 17 · 300 ms at p95 with 200 concurrent talkgroups per site
      ⇒ L4_specified
```

Each line pairs the question with what it produced. A reader who has never heard
of the system understands it from this block alone, which is why it belongs in
the demonstration and in the progression report.

**Required.** The report includes one trajectory per subject that advanced at
least two levels during the run, generated from the graph.

## A3. Refinement is not monotonic

A subject can go backwards, and pretending otherwise is a lie the system will be
caught in. If an arbitration invalidates a framing statement, or a decomposition
turns out to have missed a part, the subject is **demoted** and everything
recorded below the new level is flagged rather than deleted.

```
elicit demote floor-control --to L2_decomposed --as sofia \
  --reason "the decomposition missed the interworking case; arbitration and
  queueing do not cover a floor request originating on the LMR side"
```

Consequences, all recorded:

- the subject returns to the named level;
- statements recorded at higher levels are marked `under_review`, not withdrawn —
  they may well survive the re-decomposition;
- sections depending on the subject fall back to provisional, and the plan says
  why;
- the questions that were closed at the higher levels reopen, carrying their
  previous answers as prior context so the expert is not asked from scratch.

That last point matters: a demotion must not feel like a punishment for having
answered. The expert sees "here is what you said before, what changes given the
interworking case".

## A4. Acceptance tests, part A

1. `test_question_respects_level_scope` — a question generated for an `L2`
   subject contains no threshold, unit or technology name.
2. `test_template_violation_is_rejected` — a crystallisation breaching `forbids`
   is retried once then fails, and never reaches the mailbox.
3. `test_trajectory_orders_by_level_then_time` — the trajectory of a subject that
   advanced three levels shows three questions of increasing specificity.
4. `test_demotion_flags_but_does_not_delete` — statements above the new level are
   `under_review` and still readable.
5. `test_demotion_reopens_questions_with_prior_answers` — the reopened question
   carries the previous answer as context.

---

# Part B — Unsolicited contributions

## B1. Why this needs its own path

Everything today enters through an answer to a question the system asked. That
covers the engagement's own experts and nothing else. But the most valuable input
often comes from someone the engagement never thought to ask: a security
specialist who ran a similar accreditation, an architect from another region who
has the vendor's real interface limitations in a note, someone who simply reads
the draft and has a document that settles a point.

They cannot answer a question because none was routed to them. They have
**material**, not an answer. And their material must not enter the graph
directly: an outsider does not know the canonical vocabulary, the scope, or what
has already been decided, and letting them write would poison exactly what the
elicitation is protecting.

So: a second entry path, with a triage step and an approval, and no shortcut into
the graph.

## B2. Lifecycle

```
submitted → triaged → crystallised → confirmed by the author → accepted by the lead
```

Each transition is recorded with an actor. A contribution can leave the pipeline
at any point, and leaving is not a failure — a declined contribution with a
reason is worth keeping, because the same material will be offered again.

```
elicit submit --engagement nordwave-mcx-2027 --as external:m.okonkwo \
  --title "ENM northbound export limits observed on release 23.4" \
  --material notes/enm-export-limits.md \
  --attach diagrams/enm-export-flow.png \
  --relates-to lmr-interworking
```

`--relates-to` is optional and is a hint, not a binding: the contributor may not
know the right subject, and guessing badly must not be penalised.

## B3. Triage, by the lead architect

```
elicit contributions --engagement nordwave-mcx-2027 [--status submitted]
elicit triage CT-0004 --as sofia --accept    --to-subject lmr-interworking
elicit triage CT-0004 --as sofia --decline   --reason "..."
elicit triage CT-0004 --as sofia --redirect  --to-engagement other-2026
elicit triage CT-0004 --as sofia --to-knowledge-base
```

Four outcomes, and the fourth is the interesting one. Material that is not about
this engagement at all but is generally true — a vendor's real interface limits,
a hardening baseline — belongs in the knowledge base, not in the engagement
graph. It leaves this pipeline and enters the normal promotion route: a pull
request against the base, reviewed by a core owner.

Triage is a duty of the section owner, or of the chief architect where no section
owner exists. It is timeboxed: a contribution untriaged after a configurable
period appears in the plan as an ageing item, because an ignored contributor does
not contribute twice.

## B4. Crystallisation, and who confirms what

Two distinct confirmations, and conflating them would be the design error here.

**The author confirms the meaning.** The system proposes candidate statements
from the material and shows them to the *contributor*, not to the lead. Only the
author can say whether the extraction represents what they meant. This is the
same rule as for a solicited answer, and it applies with more force to material
written for another purpose, from which meaning is easier to distort.

**The lead accepts the entry.** Once the author has confirmed the extraction, the
lead architect decides whether it enters the engagement — a separate judgement
about relevance, scope and timing, not about meaning.

```
elicit crystallise CT-0004                      # proposes statements
elicit confirm-contribution CT-0004 --as external:m.okonkwo --accept
elicit accept CT-0004 --as sofia --section 4.5
```

If the author never confirms, nothing enters. A contribution whose author has
gone silent stays as attached material, readable and citable, with no statements
derived from it. That is an acceptable end state and must be reported as such
rather than forced through.

## B5. Vocabulary protection

An external contribution **may not create a subject**. It may only propose one,
and the proposal is part of what the lead accepts or refuses.

The crystallisation step maps the contributor's terms onto canonical subjects and
reports what it could not map:

```
mapped     "interworking gateway" → lmr-interworking
mapped     "the EMS"              → ericsson-enm
unmapped   "profile store"        → proposes new subject, requires lead approval
```

Without this rule an open contribution channel becomes a vocabulary pollution
channel, and contradiction detection — which depends entirely on subjects being
the same object — degrades silently. This is the single largest risk of opening
the path at all.

## B6. Material that is a diagram

Do not parse the diagram. A wrong extraction from an image is invisible: nobody
notices that the system misread a box.

The diagram is attached as evidence and cited by the statements derived from it,
and the contributor is asked to state in prose what it asserts — three or four
sentences. Those sentences are what gets crystallised. Where the engagement
already holds statements on the subject, the better move is the inversion
specified earlier: render our own diagram from the recorded statements and ask
the contributor to correct it, since a wrong rendering is glaring where a wrong
reading is not.

## B7. A contribution that contradicts

An outside contribution that contradicts existing statements is the most valuable
kind, and it goes through the ordinary machinery: once accepted, its statements
land, and `check_node` detects the contradiction like any other. The conflict is
marked `origin: detected` and carries the contribution as its source.

One nuance: an outsider contradicting a decided subject is often contradicting
something the engagement settled deliberately, for reasons they do not have. The
conflict card must therefore surface the arbitration history of the contested
statement, so that the lead is not re-litigating a settled question without
knowing it was settled.

## B8. Attribution and noise

The contributor is recorded as the author of every statement derived from their
material, and their verbatim is retained. At harvest, an external contribution
that proved valuable is a first-class promotion candidate — it is, almost by
definition, knowledge that was already general.

Against noise: submissions require a title and material, are triaged in batches
rather than on arrival, and the channel can be closed per engagement by the lead.
The plan reports the submission backlog and its age.

## B9. Roles, updated

| Role | Can submit | Can answer questions | Can triage | Can arbitrate |
|---|---|---|---|---|
| Contributor (routed) | yes | yes, in their domain | no | no |
| External contributor | yes | no — none is routed to them | no | no |
| Section owner | yes | yes | yes, in their section | no |
| Chief architect | yes | discouraged | yes | yes |

The "discouraged" is deliberate and belongs in the tooling: when a chief
architect answers a question routed to someone else, the system records it and
the plan shows it. The drift is predictable — they know the subject and they are
faster — and it quietly turns a collective instrument back into a single-author
document.

## B10. Acceptance tests, part B

6. `test_external_cannot_write_directly` — a submission creates no statement and
   no subject before triage.
7. `test_author_confirms_meaning_lead_accepts_entry` — statements are recorded
   only after both, in that order.
8. `test_unconfirmed_contribution_stays_as_material` — no statements, material
   readable and citable, reported as pending.
9. `test_external_cannot_create_subject` — an unmapped term produces a proposal
   requiring lead approval, never a subject.
10. `test_contradicting_contribution_detected_and_shows_history` — the conflict
    card includes the arbitration history of the contested statement.
11. `test_declined_contribution_is_retained_with_reason` — nothing is deleted.
12. `test_chief_architect_answering_is_recorded` — answering a question routed to
    another role is permitted, logged, and visible in the plan.

## B11. Prohibitions

- No external material creates a subject, a statement or an asset without both
  confirmations.
- No diagram is parsed into statements.
- No contribution is deleted; declining records a reason.
- The chief architect's arbitration of a conflict arising from their own accepted
  contribution requires a second arbitrator. Nobody arbitrates their own
  material.
