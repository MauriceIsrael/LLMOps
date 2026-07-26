---
id: TPL-scenario-mcx
title: Nordwave MCX — target behaviour scenario
type: template
status: draft
confidence: assumed
phase: [BUILD]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-26
related: [TPL-elicitation-proto]
---

> ## ⚠ This is fiction, not a transcript
>
> Every command output below was **written by hand**, not produced by running the
> system. The questions, the expert answers, the gap counts, the timings and the
> word counts are all invented. Nothing here is evidence that the implementation
> behaves this way.
>
> What it is: a **specification of target behaviour, written as a narrative**,
> because a story exposes gaps that an abstract specification hides. Read it as
> a definition of done, and treat any divergence when you run it as information
> about which of the two is wrong — the code or this document.
>
> Section 9 lists where the real run is most likely to differ, and why.

# Integration scenario — Nordwave MCX, from an empty engagement

A fictional national public-safety operator, **Nordwave**, is procuring a
mission-critical mobile network. Nothing exists in the engagement graph: no
subject, no statement, no question. This scenario runs the system from that
state and is designed to exercise what a trivial demonstration cannot —
**refinement**, **level-gated question generation**, and a **conflict that
arrives late, on a specific statement, from someone who was never asked**.

Every step names what it demonstrates. If a step passes without demonstrating
it, the implementation is wrong even though the command returned zero.

## Cast

| Person | Role | Owns |
|---|---|---|
| Amina Duarte | `mcx-service-architect` | the mission-critical service layer |
| Rui Vasconcelos | `mobile-core-architect` | the core network and bearers |
| Sofia Lindqvist | `chief-architect` | arbitration, claims, the harvest |

Local mode throughout: one machine, `--as`, no accounts.

## Seed

Only a brief. `projects/nordwave-mcx-2027/brief.yaml`, deliberately thin — this
is what an engagement actually looks like on day one.

```yaml
id: nordwave-mcx-2027
client: Nordwave (fictional)
context:
  summary: >-
    National public-safety operator replacing a legacy land mobile radio network
    with a 3GPP mission-critical service over a dedicated mobile core.
  constraints:
    - constraint: Legacy LMR fleet stays in service for at least four years
      evidence: stated-by-client
    - constraint: National sovereignty requirements on subscriber data
      evidence: stated-by-client
domains:
  - name: mcx-services
  - name: mobile-core
  - name: transport
scope:
  in: [mission-critical push-to-talk, data and video, LMR interworking]
  out: [radio access dimensioning, terminal procurement]
open_questions: []
```

No subject exists yet. The domains are names, not subjects.

---

## Act 1 — the first scan, on an empty graph

```bash
poetry run elicit scan --engagement nordwave-mcx-2027
```

```
Scanning nordwave-mcx-2027 — 9 configured sections, 0 subjects, 0 statements

  gaps found                    31
  suppressed by level gate      27
  dispatched                     3   (cap 8)

Created subjects at L0 from the brief: mcx-services · mobile-core · transport

Q-0001  L1 framing   mcx-services   → mcx-service-architect   blocks 4.1 4.3 4.5
Q-0002  L1 framing   mobile-core    → mobile-core-architect   blocks 5.1 5.3
Q-0003  L1 framing   transport      → mobile-core-architect   blocks 5.4
```

> **What this demonstrates.** Thirty-one gaps exist and three questions are sent.
> The twenty-seven others are not capped away — they are **suppressed by the
> level gate**, because they ask things that cannot be asked of a subject nobody
> has framed yet. Run `elicit gaps --show-suppressed` and the reasons must be
> visible:
>
> ```
> held  parameter  "floor control latency budget"      subject floor-control does not exist
> held  mechanism  "how is priority enforced"          subject mcx-services is at L0, needs L2
> held  decision   "which interworking gateway"        subject interworking does not exist
> ```
>
> A demonstration that produces one question on an empty engagement has not
> tested the gate; a demonstration that produces thirty-one has failed it.

---

## Act 2 — framing, and prose that looks like an architect wrote it

Amina opens Q-0001.

```
┌─ Q-0001 ──────────────────────────── L1 framing · blocks 4.1, 4.3, 4.5 ─┐
│                                                                          │
│  What is the mission-critical service layer for at Nordwave, and what    │
│  must keep working when everything else degrades?                        │
│                                                                          │
│  Why this matters                                                        │
│    Nothing can be decomposed or decided before the boundary and the      │
│    survival requirement are stated. Sections 4.1, 4.3 and 4.5 all        │
│    depend on this.                                                       │
│                                                                          │
│  Please use these terms                                                  │
│    mcx-services · mission-critical · degraded-mode                       │
│                                                                          │
│  Expected                                                                │
│    the purpose, the boundary, and what must survive — in prose           │
│                                                                          │
│  Previously answered elsewhere                                           │
│    nothing yet — this is the first engagement to frame this subject      │
│                                                                          │
│  Constrained by  P-009                                                   │
│  Context  no statements recorded yet about mcx-services                  │
└──────────────────────────────────────────────────────────────────────────┘
```

```bash
poetry run elicit answer Q-0001 --as amina --engagement nordwave-mcx-2027 --text "
The MCX layer delivers group voice, data and video to dispatchers and field
teams, and it has to keep delivering group voice when almost nothing else works.
Our boundary is the 3GPP MC service layer: group and affiliation management,
floor control, media distribution, and the interworking function towards the
legacy LMR fleet, which stays for four more years. Everything below — bearers,
QoS, slices — belongs to the core team.

What must survive is talkgroup communication inside an isolated site: if the
transport to the national data centres is cut, a site must keep serving its
local talkgroups. That is a hard requirement from the customer, and I do not yet
know whether the platform we shortlist can do it without a local instance."
```

```
Proposed statements — nothing recorded until you confirm.

  S-0001  mcx-services · is_constrained_by · "3GPP MC service layer boundary:
          group management, floor control, media distribution, LMR interworking"
          confidence: designed

  S-0002  mcx-services · has_property · "group voice must survive site isolation
          from the national data centres"
          confidence: stated-by-client       ← flagged: the answer attributes
                                               this to the customer, not to design

  S-0003  mcx-services · depends_on · "legacy LMR fleet in service ≥ 4 years"
          confidence: stated-by-client

  ⚠ One passage was not extracted as a statement:
    "I do not yet know whether the platform we shortlist can do it without a
     local instance" — recorded as an open uncertainty on mcx-services, not as
     a fact. It will generate a question when the subject reaches L3.

  Your words kept in full.
```

```bash
poetry run elicit confirm Q-0001 --accept --as amina --engagement nordwave-mcx-2027
```

```
3 statements recorded · 1 uncertainty recorded
mcx-services  L0 → L1 (framed)
```

> **What this demonstrates.** The extraction distinguished a design decision from
> a customer statement and assigned different confidence to each — the reason
> `confidence` exists as a field. And it refused to turn an admitted unknown into
> a fact, parking it instead as an uncertainty that will resurface at the right
> level. A demonstration whose answer is four words cannot show either.

---

## Act 3 — decomposition, and the base admitting it has nothing

The next scan sees `mcx-services` at L1 and now asks the L2 question.

```bash
poetry run elicit scan --engagement nordwave-mcx-2027
```

```
Q-0007  L2 decomposition   mcx-services   → mcx-service-architect   blocks 4.1 4.3 4.5
Q-0008  L1 framing         interworking   → mcx-service-architect   blocks 4.5
        (subject created by S-0001)
```

Amina decomposes:

```bash
poetry run elicit answer Q-0007 --as amina --engagement nordwave-mcx-2027 --text "
Four parts. Group and affiliation management, which is mostly a data problem and
talks to the subscriber database. Floor control, which is the latency-critical
one and the reason people will judge the system. Media distribution, where the
question is unicast versus multicast on the radio side. And the LMR interworking
function, which is a gateway to a vendor system we do not control.
"
```

```
Proposed: mcx-services decomposes into 4 parts
  → group-management · floor-control · media-distribution · lmr-interworking
  each created at L0

Candidate patterns for this decomposition:
  none in the base — no pattern matches a mission-critical service decomposition.
  This is the first engagement to record one. If it recurs, it becomes a
  promotion candidate at the harvest.

However, one part matches an existing pattern:
  lmr-interworking  →  PAT-006  Vendor boundary through the northbound interface
    "A vendor system owns a domain the chain must nonetheless observe and act on."
    when not to use it: "where the vendor supports and documents direct
    model-driven access with equivalent guarantees."
    → proposed as a candidate shape, to confirm or discard at L3.
```

```bash
poetry run elicit confirm Q-0007 --accept --as amina --engagement nordwave-mcx-2027
```

```
4 subjects created · mcx-services  L1 → L2 (decomposed)
Level gate released: 6 previously held questions are now askable.
```

> **What this demonstrates.** Three things a staged scenario never shows. The
> decomposition **created subjects**, which is what unlocks the next wave of
> questions — refinement is generative, not just a status change. The base was
> **honest about having nothing**: no invented pattern, and an explicit note that
> this decomposition is itself a candidate for promotion. And a pattern from a
> completely different domain matched one part, which is the reuse the whole base
> exists for — the analogy is structural, not topical.

---

## Act 4 — the board, mid-engagement

```bash
poetry run elicit subjects --engagement nordwave-mcx-2027
```

```
subject               L0  L1  L2  L3  L4   blocked by              sections
mcx-services          ██  ██  ██  ··  ··   Q-0011 · amina          4.1 4.3 4.5
floor-control         ██  ··  ··  ··  ··   Q-0012 · amina          4.3
media-distribution    ██  ··  ··  ··  ··   Q-0013 · amina          4.3
group-management      ██  ··  ··  ··  ··   —  (not yet dispatched, cap)   4.1
lmr-interworking      ██  ··  ··  ··  ··   Q-0014 · amina          4.5
mobile-core           ██  ██  ··  ··  ··   Q-0009 · rui            5.1 5.3
transport             ██  ··  ··  ··  ··   Q-0003 · rui ⚠ 6 d      5.4

7 subjects · 0 at L3 or beyond · no section can render as final
```

> **What this demonstrates.** The overview answers "what is left to instruct"
> without listing questions. It also shows the load imbalance immediately: five
> open questions on Amina, two on Rui, one of them stalled six days. That is the
> number a weekly review acts on.

---

## Act 5 — a decision, and an argument that arrives sideways

Amina takes floor control through framing and decomposition, then decides where
it terminates.

```bash
poetry run elicit answer Q-0021 --as amina --engagement nordwave-mcx-2027 --text "
Floor control terminates in the MC service layer, at the site. We keep the floor
arbitration local so that a site cut off from the national data centres still
grants and revokes the floor for its own talkgroups. We rely on the core only
for bearer establishment and for priority marking, not for the arbitration
itself.
"
poetry run elicit confirm Q-0021 --accept --as amina --engagement nordwave-mcx-2027
```

```
S-0034  floor-control · has_property · "arbitration terminates in the MC service
        layer, at the site"  · designed
floor-control  L2 → L3 (decided)
```

Four days later Rui, who was never asked about floor control, reads the draft
section and contests a specific statement.

```bash
poetry run elicit contest S-0034 --as rui --engagement nordwave-mcx-2027 --text "
I do not disagree with local arbitration, but 'we rely on the core only for
priority marking' hides a real dependency. Under congestion the floor grant is
useless if the bearer is not admitted, and admission is an ARP decision in the
core. If we state floor control as independent of the core, section 5.3 will
under-specify the priority and pre-emption profile and we will discover it in
acceptance testing. My position is that floor control depends on a committed
pre-emption profile, and that profile is a core deliverable.
"
```

```
S-0041  floor-control · depends_on · "committed priority and pre-emption profile
        in the core"  · rui · designed

⚠ CONTRADICTION  C-0003

  subject    floor-control
  predicate  has_property / depends_on — same aspect, incompatible scope

  S-0034  "arbitration terminates in the MC service layer, at the site"
          amina · mcx-service-architect · designed · day 12
  S-0041  "depends on a committed pre-emption profile in the core"
          rui · mobile-core-architect · designed · day 16

  Advisory: these are not mutually exclusive. They may be reconciled by
  narrowing S-0034 to arbitration rather than to end-to-end floor grant.
  For the arbitrator, not a verdict.

  Both statements remain active. Section 4.3 renders both and is contested.
  Routed to: sofia, amina, rui
```

> **What this demonstrates.** The conflict arrived **four days later**, from
> someone who **was never asked the question**, about a **specific statement**
> rather than a whole answer — which is how architecture disagreements actually
> occur. And the advisory note proposes a reconciliation rather than a winner,
> because the two positions are not in fact exclusive. A scenario where two
> people answer the same question and one is simply wrong tests none of this.

---

## Act 6 — arbitration that changes both statements

```bash
poetry run elicit arbitrate C-0003 --as sofia --engagement nordwave-mcx-2027 \
  --amend S-0034 --to "floor arbitration terminates in the MC service layer at the site" \
  --keep S-0041 \
  --reason "Both are right and the disagreement is one of scope. Arbitration is
  local; the end-to-end floor grant is not, because it depends on admission in
  the core. S-0034 is narrowed to arbitration. S-0041 stands and becomes a
  commitment on the core side: the pre-emption profile is now a deliverable of
  section 5.3, with an acceptance criterion. Raised as a risk: this dependency
  was implicit until day 16 and would have surfaced in acceptance testing."
```

```
C-0003 arbitrated by sofia
  S-0034  amended, active, previous wording kept in history
  S-0041  kept, active
  R-07    new risk recorded: cross-layer dependency discovered late
  Q-0028  created on mobile-core: "pre-emption profile: which ARP mapping per
          talkgroup class?"  → rui  blocks 5.3
```

> **What this demonstrates.** Arbitration is not a winner-takes-all switch. It
> amended one statement, kept the other, created a risk and generated a new
> question on another subject. That is what an architect actually does with a
> disagreement, and it is the strongest argument for recording the exchange.

---

## Act 7 — assembly, and why it is still provisional

```bash
poetry run elicit assemble --engagement nordwave-mcx-2027
```

```
Rendered 9 sections · 3 118 words

  status      PROVISIONAL
  reason      not conflicts — 4 subjects below L3
              group-management L0 · media-distribution L1 · transport L1 · lmr-interworking L2

  section 4.3  final     floor-control and its dependency are decided
  section 4.1  provisional   group-management not yet framed
  section 4.5  provisional   lmr-interworking decomposed but not decided
  section 5.3  provisional   Q-0028 open

  open conflicts  0
  open questions  6 · oldest 9 days · Q-0003 with rui
```

> **What this demonstrates, and it is the most important step.** The document is
> provisional **because subjects are immature**, not because a conflict is open.
> Arbitrating one disagreement did not flip a whole document to complete — that
> is the tell of a staged scenario. Section 4.3 alone reached final, because its
> subject reached L3 and its dependency was resolved.

---

## Act 8 — the harvest, which is what makes any of this worth doing

```bash
poetry run elicit harvest --engagement nordwave-mcx-2027 --as sofia
```

```
Promotion candidates:
  · decomposition of a mission-critical service layer into group management,
    floor control, media distribution and interworking — first occurrence,
    hold until a second engagement
  · PAT-006 matched a domain it was not written for; add the occurrence to its
    "seen in" section
  · C-0003 pattern: cross-layer dependency implicit until contested → candidate
    for a new gap rule "a subject decided at L3 with a dependency on another
    subject below L3"

Evidence recorded:
  · R-07 materialised in this engagement
  · effort actuals: none yet, phase not closed
```

> **What this demonstrates.** The conflict itself produced a reusable insight:
> a new gap detection rule. That is the base learning from an argument, which is
> the difference between a knowledge base and a filing cabinet.

---

## 9. Where the real run will differ from this fiction

Written before anyone runs it, so that it cannot be adjusted afterwards.

**The numbers are decoration.** 31 gaps, 27 suppressed, 3 118 words, "9 days" —
all invented. What matters is the ratio and the visibility of the suppression
reasons, not the values.

**The extraction will be worse than written.** Act 2 shows an extraction that
cleanly separates a design decision from a customer statement, assigns different
confidence to each, and parks an admitted uncertainty rather than promoting it to
fact. That is the behaviour to aim for. A first implementation will more likely
merge the two constraint statements, flatten the confidence to a single value,
and either drop the uncertainty or record it as a statement. This is the single
most probable divergence, and the most worth fixing.

**The pattern match may not happen at all.** `PAT-006` matching `lmr-interworking`
requires semantic matching between a pattern's problem statement and a fresh
decomposition. If the implementation only matches on subject names or domains,
it will find nothing — which is not a failure of the idea, only of the retrieval.
Check whether a spurious match appears instead: a confident wrong pattern is
worse than none.

**The conflict of Act 5 would not fire under the rule as specified.** The
specification defines a contradiction as *same subject, same predicate,
different value*. C-0003 opposes a `has_property` statement to a `depends_on`
statement — different predicates. Under the current rule the two would coexist
silently, and the disagreement would surface only in review.

This was found by writing the narrative, not by reading the specification, and
it is the main reason this file exists. Two possible resolutions, and the choice
belongs to whoever implements it:

- widen the rule to *same subject, overlapping aspect*, accepting more false
  positives and needing a notion of aspect beyond the predicate;
- keep the rule narrow and accept that cross-predicate tensions are caught by
  the advisory semantic pass rather than by query — which contradicts the
  determinism boundary and should then be stated as a known limit.

**`--amend` does not exist yet.** The option was invented while writing Act 6 and
retro-fitted into the specification afterwards. It is a target, not a feature.

**The harvest will not derive a new gap rule on its own.** Act 8 shows the system
proposing a rule inferred from the shape of a conflict. Realistically a human
notices that and writes it. Keep the step, expect to do the thinking.

## Acceptance criteria for this scenario

Run it end to end. It has passed only if all of these hold.

1. The first scan dispatches 3 questions and suppresses more than 20, with
   visible reasons.
2. At least one question is held by the level gate and later released by a
   decomposition, and the release is observable.
3. An extraction assigns different confidence to two statements from one answer.
4. An admitted uncertainty is recorded as such and not as a fact.
5. A pattern from an unrelated domain is proposed at L2, with its "when not to
   use" section.
6. The base explicitly reports having no matching pattern for the decomposition.
7. The contest targets a statement, comes from someone not asked, and arrives
   after a delay.
8. Arbitration amends one statement, keeps another, creates a risk and a
   question.
9. Assembly is provisional for a maturity reason, with per-section status.
10. The harvest proposes a new gap rule derived from the conflict.

A run that reaches `COMPLETE` is a failed run: this engagement is not finished,
and a system that claims otherwise is lying to its user.
