---
id: TPL-mailbox-rendering
title: Mailbox rendering — specification supplement
type: template
status: draft
confidence: verified
phase: [BUILD]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-26
related: [TPL-elicitation-proto]
---

# Mailbox rendering — specification supplement

Complements `TPL-elicitation-proto`. Adds the rendering of elicitation artefacts
as Markdown cards posted to a mailbox, and the command protocol that lets an
expert answer, confirm, contest and arbitrate without leaving that mailbox.

The purpose is not cosmetic. The prototype's interaction is currently invisible:
identifiers travel, artefacts do not. Rendering the cards makes the four things
that matter visible — the question and its stakes, the extraction before it is
recorded, the two sides of a conflict, and the arbitration rationale — and it
does so without building any interface.

`WORKED-EXAMPLE.md` is the reference rendering. The Markdown must carry the same
blocks in the same order; only the presentation changes.

---

## 1. Scope

**In scope.** Four card renderers, one command parser, a GitHub Issues adapter,
a file adapter for offline work, and the identity mapping between platform
accounts and elicitation roles.

**Out of scope.** Any web interface. Any rendering performed by a model. Any
storage of domain state in the mailbox.

---

## 2. The cards

Four renderers, each a pure function from a domain object to a Markdown string.
Deterministic, no network, no model, unit-testable against golden files.

```python
def render_question(q: Question, frame: QuestionFrame) -> str: ...
def render_proposal(q: Question, statements: list[Statement], verbatim: str) -> str: ...
def render_conflict(c: Conflict, statements: list[Statement], advisory: str | None) -> str: ...
def render_arbitration(c: Conflict, kept: Statement, superseded: Statement) -> str: ...
```

### 2.1 Question card — required blocks, in this order

1. **The question**, as a level-3 heading. One sentence. Nothing above it.
2. **Why this matters** — the stake and the sections blocked. Two sentences at
   most. If it takes more, the gap was not properly crystallised.
3. **Please use these terms** — the canonical subject and related glossary
   terms, as inline code so they are visually distinct from prose.
4. **Expected** — the shape of the answer, in plain words.
5. **Previously answered elsewhere** — where the base has a prior answer: the
   engagement, the value, its confidence, and an explicit invitation to confirm
   or diverge. Omit the block entirely when there is no prior answer; an empty
   section teaches the reader to skip the section.
6. **Constrained by** — asset identifiers, as links to the knowledge base.
7. **How to answer** — the command, pre-filled, ready to copy.

### 2.2 Proposal card

The extraction, always posted before anything is recorded. Required: each
candidate statement as `subject · predicate · value` with its confidence and the
assets it is based on; the contributor's verbatim quoted below, unmodified; and
the three available commands. It must state, in words, that nothing is recorded
yet.

### 2.3 Conflict card

Required: the contested subject and predicate; the two statements side by side
with author, role, confidence and date; any advisory note from the coherence
pass, explicitly labelled as advisory and not a verdict; a sentence stating that
both statements remain active; and the arbitration command with a mandatory
`--reason`.

### 2.4 Arbitration card

Required: what was kept, what was superseded, by whom, and the rationale
verbatim. Must state that the superseded statement remains in the history and is
a promotion candidate if it proves right elsewhere. Losing an arbitration should
not feel like being erased.

### 2.5 Rendering rules

- Portable Markdown only. It must read correctly on the platform, in a terminal
  and in a plain text editor. No raw HTML except the invisible marker of §4. No
  `<details>` blocks: they hide exactly what this exercise exists to show.
- Internal identifiers appear as secondary references, never as the primary
  handle. `Q-0001` is acceptable; a timestamp-derived statement id is not — mint
  short sequential identifiers per engagement.
- Never render a prompt, a model rationale, or a token count. The reader is an
  architect, not an operator of the pipeline.
- Line length wrapped at 88 characters in the source, so that diffs of the
  templates stay readable.

---

## 3. Command protocol

Experts act by leaving a comment. The parser accepts a command only when it is
the **first non-empty line** of the comment, so that quoting a previous message
or discussing a command in prose never triggers it.

| Command | Who | Effect |
|---|---|---|
| `/answer <free text>` | routed role | Runs the intake flow, posts the proposal card |
| `/confirm` | the author of the answer | Resumes the interrupted flow, records the statements |
| `/edit` + a fenced YAML block | the author of the answer | Resumes with a corrected statement set |
| `/reject <reason>` | the author of the answer | Discards the extraction, keeps the verbatim, reopens the question |
| `/contest <statement-ref> <free text>` | any contributor | Records a competing statement about the same subject |
| `/reroute <role-or-person> <reason>` | routed role | Reassigns without creating a gap; records who declined and why |
| `/decline <reason>` | routed role | Records a declared unknown, which is information and appears in the document |
| `/arbitrate keep <statement-ref> --reason <text>` | chief architect only | Resolves the conflict |

Rules that are not negotiable:

- A command from an account whose mapped role is not authorised is **refused
  with a comment naming the required role**. Never ignore it silently — silence
  is indistinguishable from a bug and the contributor will assume it worked.
- `/arbitrate` without `--reason` is refused. The rationale is the deliverable,
  not the decision.
- `/confirm` is refused if the flow is not paused at the confirmation interrupt,
  with a comment explaining the current state.
- Multi-line free text after a command is preserved whole, including line
  breaks, as the verbatim.

**Rejected alternative.** Task-list checkboxes to accept individual statements
were considered and rejected: the platform's edit events make it unreliable to
attribute a toggle to a person, and attribution is the point. Checkboxes may be
used for display, never for action.

---

## 4. Idempotency and the direction of truth

Kùzu is the source of truth. The mailbox is a projection of it. This direction
never reverses, and three mechanisms enforce it.

Every posted body carries an invisible marker as its first line:

```
<!-- elicit:demo-2026:Q-0001:question:sha=8f3a2c -->
```

Posting is therefore an upsert: find the marker, compare the hash, update in
place if the content changed, do nothing if it did not. Re-running a scan must
never duplicate a card.

If a human edits a rendered card, the next synchronisation re-renders it from
the domain state and appends a short comment noting that an edit was overwritten
and where the content actually lives. Editing the card is a natural reflex and
must not silently diverge.

If the mailbox is unreachable, questions are still persisted and queued with a
`pending_dispatch` status. A question is never lost because a platform was down.

---

## 5. GitHub Issues adapter

| Domain object | GitHub object |
|---|---|
| Question | One issue, title `[Q-0001] <question, truncated to 60 chars>` |
| Question routing | Assignee resolved from the role mapping; labels `role:<role>`, `section:<id>`, `engagement:<id>` |
| Blocking impact | Label `blocks:<n>` so a queue can be sorted by consequence |
| Answer | Comment with `/answer` |
| Proposal | Bot comment |
| Confirmation | Comment with `/confirm`, then the issue is closed |
| Conflict | Separate issue, title `[C-0001] contested: <subject>`, assigned to the chief architect, linking both statements and the originating questions |
| Arbitration | Comment with `/arbitrate`, then the conflict issue is closed |
| Declared unknown | Issue closed with label `declared-unknown`, and it stays visible in the document |

Two constraints. The mailbox repository is **private**, because verbatim answers
carry engagement material — this is not optional and is checked at startup.
Webhooks are preferred over polling; if polling is used, keep the interval above
sixty seconds and honour rate limits.

The identity mapping lives in `projects/<engagement>/roster.yaml`:

```yaml
- login: alice-gh
  name: Alice
  roles: [cloud-architect]
- login: charlie-gh
  name: Charlie
  roles: [chief-architect, network-architect]
```

An unmapped account attempting a command receives a comment explaining how to be
added. Roles, not people, are what questions are routed to; the roster resolves
the rest.

## 6. File adapter

`FileMailbox` writes the identical Markdown under
`projects/<engagement>/mailbox/`, one directory per question, and reads commands
from a `commands.md` file. It exists so that the whole scenario runs offline, in
tests, and in a demonstration without network access — and so that the golden
files used to test rendering are the very artefacts a reviewer reads.

---

## 7. Templates

One file per card under `tools/elicitation/mailbox/templates/`, rendered with a
plain template engine. Each template begins with a comment documenting its
variable contract. Templates are data, not code: adding a block to a card must
never require touching the renderer.

Golden files under `tests/golden/` hold the expected output of each card for a
fixed fixture. A rendering change that alters a golden file must update it in
the same commit, so that the diff of the artefact is reviewable — the cards are
the user interface, and they deserve to be reviewed as such.

---

## 8. Acceptance tests

1. `test_question_card_matches_golden` — full card against the fixture.
2. `test_question_card_omits_empty_prior_block` — no prior answer, no section.
3. `test_card_is_idempotent` — posting twice updates once, no duplicate.
4. `test_manual_edit_is_restored` — edited body is re-rendered and a note posted.
5. `test_command_must_be_first_line` — a quoted `/confirm` inside prose does not
   trigger.
6. `test_unauthorised_role_is_refused_loudly` — a comment is posted naming the
   required role.
7. `test_arbitrate_requires_reason` — refused, with an explanatory comment.
8. `test_verbatim_survives_edit` — after `/edit`, the original words are still
   attached to the statements.
9. `test_dispatch_queues_when_mailbox_down` — question persisted with
   `pending_dispatch`, delivered on the next run.
10. `test_file_and_github_render_identically` — both adapters produce the same
    Markdown body for the same object.

## 9. Prohibitions

- No model is called during rendering. Cards are deterministic.
- No domain state is read back from the mailbox.
- No card is posted for an object that has not been persisted first.
- No silent refusal of a command.
- No public repository as a mailbox.

## 10. Deliverables

The four renderers, the templates and their golden files, the command parser,
both adapters, the roster schema, the ten tests passing, and one screenshot of a
real question issue added to `WORKED-EXAMPLE.md`. That screenshot is the point of
the whole supplement: it is what makes the idea legible to a colleague who will
never run the command line.
