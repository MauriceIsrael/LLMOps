---
id: TPL-fixes-scan
title: scan.py — defect report and fix specification
type: template
status: active
confidence: verified
phase: [BUILD]
domain: [ai-assistance]
owner: core-owner-automation
last_reviewed: 2026-07-27
related: [TPL-elicitation-proto, TPL-planning-and-demo]
---

# scan.py — defect report and fix specification

Work order for the coding agent. Ten defects, reviewed on the version of
`tools/elicitation/flows/scan.py` dated 2026-07-27. Three of them mean the scan
does not currently detect anything: it replays a fixture written in the source.

Fix in the order given. D1 to D4 must be done together — fixing one without the
others leaves the module in a worse state than it is now, because the counts
would reconcile against a catalogue that is still hardcoded.

**Out of scope for this pass.** Do not touch `flows/intake.py`,
`flows/assemble.py` or the repository's write methods beyond the signature change
of D6. This is a rewrite of gap detection, not of the pipeline.

---

## Priority summary

| # | Defect | Severity | Consequence |
|---|---|---|---|
| D1 | The gap catalogue is a hardcoded list of 35 specifications | critical | The system does not detect gaps; it enumerates a fixture |
| D2 | The document blueprint is hardcoded in `load_frame_node` | critical | The deliverable's structure cannot vary per engagement |
| D3 | The level gate exempts three subjects by name | high | Always the same three questions; the gate is not uniform |
| D4 | Suppressed gaps are dropped by `continue`, not held | high | Counts do not reconcile; suppressions are invisible |
| D5 | `blocking` and `blocking_count` are fabricated | high | Invented identifiers appear in a deliverable as facts |
| D6 | Subjects are not scoped by engagement | high | Two engagements collide in the same graph |
| D7 | Two writers open the same database in one node | medium | File-lock contention; the cause of `gc.collect()` in tests |
| D8 | Cypher built by f-string interpolation | medium | Injection, and breakage on an apostrophe in a name |
| D9 | Subject maturity queried once per section | low | N+1 queries, compounding D7 |
| D10 | Defaults mask configuration errors | medium | A missing engagement silently targets `demo-2026` |

---

## D1 — The gap catalogue is hardcoded

**Symptom.** `all_premature_specs` in `detect_gaps_node` holds 35 tuples naming
every question the system will ever be able to ask. The 26 "held gaps" reported on
the first run were 26 rows of this table whose subject happened to exist.

**Cause.** Gap detection was implemented as enumeration of known cases rather than
as evaluation of a distance between a requirement and a state.

**Required fix.** Delete the list. A gap is computed as the distance between what
the blueprint requires and what the engagement graph holds. Nothing in the source
names a section, a subject or a parameter.

**Acceptance.** Adding a section to the blueprint file, with no code change,
produces new gaps. Removing one makes its gaps disappear. This is the
discriminating test: while the catalogue exists, it fails.

---

## D2 — The blueprint is hardcoded, and the docstring is false

**Symptom.** `load_frame_node` returns nine literal sections. Its docstring claims
to load the frame "depuis Kùzu DB et le FastMCP server". It loads nothing.

**Required fix.** The blueprint is a versioned data file, bound to the engagement,
loaded by identifier. Structure, which also resolves D5:

```yaml
# blueprints/BLU-hla-mcx.yaml
id: BLU-hla-mcx
title: High-level architecture blueprint — mission-critical mobile
version: 1
sections:
  - id: "4.1"
    title: MCX services boundary and framing
    must_answer: >-
      What is the mission-critical service layer for, and what must keep working
      when everything else degrades?
    requires:
      - {subject: mcx-services, level: L1_framed}
    unlocks: ["4.2", "4.3", "4.4", "4.5", "4.6"]
    routes_to: mcx-service-architect
  - id: "4.3"
    title: Floor control arbitration
    must_answer: "Where does floor arbitration terminate, and what was ruled out?"
    requires:
      - {subject: floor-control, level: L3_decided}
    unlocks: ["4.3.1"]
    routes_to: mcx-service-architect
```

`unlocks` is declarative and is the only source of `blocking` (see D5).
`requires` may name several subjects; a section is satisfied only when all of
them meet their level.

`load_frame_node` becomes: read `state["blueprint_id"]`, load the file, validate
it against a schema, return it. If the identifier is absent, raise — see D10.
Correct the docstring to state what the function does.

**Acceptance.** `load_frame_node` contains no section literal. A blueprint failing
schema validation raises with the offending section named.

---

## D3 — The level gate exempts three subjects by name

**Symptom.**

```python
if req_lvl in (...) and subj_lvl == "L0_named" \
   and sec_sub not in ("mcx-services", "mobile-core", "transport"):
    continue
```

The three root subjects bypass the gate. This is why the same three questions come
back on every scan: they are the only ones never filtered.

**Required fix.** One rule, no exemption, no name in the condition:

```python
def gate(current_level: str | None, required_level: str) -> str | None:
    """Returns a hold reason, or None when the gap is dispatchable."""
    if current_level is None:
        return "subject does not exist yet"
    if LEVEL_INDEX[current_level] < LEVEL_INDEX[required_level]:
        return f"subject at {current_level}, needs {required_level}"
    return None
```

Root subjects need no exemption: a section requiring `L1_framed` of a subject at
`L0_named` legitimately produces a dispatchable framing gap, because framing is
what advances `L0` to `L1`. If that does not hold, the blueprint has declared the
wrong required level, and that is where to fix it.

Remove also the two other special cases in the same function: the hardcoded
`if mcx_lvl == "L1_framed"` decomposition block, and
`not (sec_id == "4.1" and mcx_lvl != "L0_named")`. Both become ordinary
consequences of the blueprint.

**Acceptance.** No subject name appears in any conditional in the module. Renaming
`mcx-services` in the blueprint and the brief changes nothing in behaviour.

---

## D4 — Suppressed gaps are dropped, not held

**Symptom.** Every rejection is a `continue`. The gap ceases to exist. The report
therefore shows one population of held gaps while another was silently discarded,
and the arithmetic never reconciles.

**Required fix.** `detect_gaps_node` returns **every** evaluated gap, each carrying
a status. Nothing is dropped.

```python
@dataclass
class Gap:
    gap_type: str            # G1_section_unsatisfied | G2_unanswered_blocking | G3_principle_unaddressed
    section: str
    subject: str
    required_level: str
    current_level: str | None
    status: str              # dispatchable | held_premature | held_queued | satisfied
    hold_reason: str | None
    blocking: list[str]      # from the blueprint's unlocks, never fabricated
    routes_to: str
```

`satisfied` is included on purpose: the plan command of
`TPL-planning-and-demo` needs to show coverage, which requires knowing what is
already met.

`counts_summary` becomes the contract:

```python
{"dispatchable": 3, "held_premature": 26, "held_queued": 0, "satisfied": 4, "total": 33}
```

with `total == sum of the others`, asserted in the node itself.

**Acceptance.** For any run, the four counts sum to the total. A gap with
`status != "dispatchable"` always carries a non-empty `hold_reason`, except when
`satisfied`.

---

## D5 — `blocking` and `blocking_count` are fabricated

**Symptom.**

```python
"blocking": [f"{sec_id}.1", f"{sec_id}.2"],
"blocking_count": 3 if sec_id.startswith("4.") else (2 if "5." in sec_id else 1),
```

The first invents section identifiers that do not exist — they appeared in the
progression report as facts. The second is a constant per prefix, so sorting by
impact measures nothing.

**Required fix.** Both come from the blueprint:

```python
blocking = section.unlocks
blocking_count = len(section.unlocks)
```

Sorting for dispatch: `blocking_count` descending, then gap age ascending.

**Acceptance.** Every identifier in `blocking` exists as a section of the bound
blueprint; assert it in the node rather than trusting it. Two sections with
different `unlocks` produce different `blocking_count`.

---

## D6 — Subjects are not scoped by engagement

**Symptom.** `repo.save_subject("mcx-services")` and
`repo.get_subject_maturity("mcx-services")` take no engagement. Subjects are
global; two engagements sharing a subject name share its maturity.

**Required fix.** Add `engagement` to the primary key of `Subject` and to every
repository method touching it. This is a data-model change, so it comes with a
migration: existing rows are attributed to the engagement they belong to, or the
database is rebuilt if it holds only demonstration data.

```python
repo.save_subject(engagement=eng, name="mcx-services", origin="blueprint")
repo.get_subject_maturity(engagement=eng, name="mcx-services")
repo.subject_levels(engagement=eng)   # see D9
```

`origin` is added while the signature is being changed: `blueprint` for subjects
created at binding, `discovered` for those created by a decomposition. The
progression report must distinguish them (see `TPL-planning-and-demo` §4.1).

**Acceptance.** Two engagements declaring `mcx-services` hold independent
maturity. A subject created by decomposition carries `origin: discovered`.

---

## D7 — Two writers on the same database

**Symptom.** `KuzuClient(db_path, read_only=False)` and
`ElicitationRepository(db_path)` are both opened inside `detect_gaps_node`.

**Required fix.** One connection per node, passed in rather than constructed. The
node receives a repository and uses only it; `KuzuClient` is an implementation
detail of the repository and is not imported by flow code. Detection reads only,
so the connection is opened read-only.

**Acceptance.** No flow module imports `KuzuClient`. Two consecutive scans in one
process succeed without `gc.collect()`, and the test suite no longer contains
`del repo`.

---

## D8 — Cypher by string interpolation

**Symptom.**

```python
q = f"MATCH (s:Statement {{engagement: '{engagement}', section: '{sec_id}', ...}}) ..."
```

**Required fix.** Parameterised queries only, through a repository method:

```python
def section_has_statements(self, engagement: str, section: str) -> bool:
    return self._one(
        "MATCH (s:Statement {engagement: $e, section: $sec, status: 'active'}) "
        "RETURN count(s) AS c",
        {"e": engagement, "sec": section},
    )["c"] > 0
```

**Acceptance.** No f-string containing `MATCH`, `CREATE` or `MERGE` remains in the
module. A subject name containing an apostrophe is handled.

---

## D9 — N+1 queries on subject maturity

**Symptom.** `get_subject_maturity` is called once per section, plus once for
`mcx-services` before the loop.

**Required fix.** One query returning the levels of all subjects of the
engagement, into a dict consulted in memory.

```python
levels: dict[str, str] = repo.subject_levels(engagement=eng)
```

**Acceptance.** A scan over a blueprint of 40 sections issues one maturity query,
verifiable by counting calls on a spy.

---

## D10 — Defaults mask configuration errors

**Symptom.** `state.get("engagement", "demo-2026")` and
`state.get("db_path", "data/kuzu_db")` in three nodes. A scan invoked without an
engagement silently operates on the demonstration engagement.

**Required fix.** Required inputs have no default. Validate the state on entry to
the first node and raise a clear error naming the missing key. Optional inputs —
`strategy`, the caps — keep defaults, taken from configuration rather than from
literals in the function body.

**Acceptance.** `scan.invoke({})` raises naming the missing keys. No literal
engagement identifier or database path appears in the module.

---

## Target shape of the module

```python
def load_frame_node(state: ScanState) -> dict:
    """Loads and validates the blueprint bound to the engagement. No I/O beyond that."""
    require(state, "engagement", "blueprint_id")
    bp = load_blueprint(state["blueprint_id"])   # schema-validated
    return {"blueprint": bp}


def detect_gaps_node(state: ScanState) -> dict:
    """Evaluates every blueprint requirement against the engagement graph.

    Pure with respect to the graph: reads only, returns every gap with a status,
    drops nothing.
    """
    repo, eng, bp = state["repo"], state["engagement"], state["blueprint"]
    levels = repo.subject_levels(engagement=eng)
    with_statements = repo.sections_with_statements(engagement=eng)   # one query

    gaps = [
        evaluate(section, req, levels.get(req.subject), section.id in with_statements)
        for section in bp.sections
        for req in section.requires
    ]
    counts = summarise(gaps)
    assert counts["total"] == sum(v for k, v in counts.items() if k != "total")
    return {"gaps": gaps, "counts_summary": counts}


def evaluate(section, req, current_level, has_statements) -> Gap:
    """One requirement, one gap record. No side effect, no query."""
```

`evaluate` being pure and query-free is what makes gap detection testable without
a database, which is the point of the refactor.

---

## Acceptance tests to add

1. `test_blueprint_change_changes_gaps` — add a section to a fixture blueprint,
   assert new gaps; remove it, assert they disappear. **The discriminating test:
   it cannot pass while a hardcoded catalogue exists.**
2. `test_no_subject_name_in_source` — grep the module for `mcx-services`,
   `mobile-core`, `transport`; assert none. Crude and effective.
3. `test_counts_reconcile` — the four statuses sum to the total on three
   different fixtures.
4. `test_every_held_gap_has_a_reason` — no held gap without `hold_reason`.
5. `test_blocking_references_existing_sections` — every entry of `blocking` is a
   section of the bound blueprint.
6. `test_gate_is_uniform` — a root subject and a discovered subject at the same
   level, with the same required level, receive the same treatment.
7. `test_subjects_are_engagement_scoped` — two engagements, same subject name,
   independent levels.
8. `test_evaluate_is_pure` — call `evaluate` with no database available.
9. `test_single_maturity_query` — one call for a 40-section blueprint.
10. `test_missing_engagement_raises` — `invoke({})` raises naming the missing keys.

---

## Prohibitions

- No section, subject or parameter name in the module's source.
- No gap discarded: every evaluation is returned with a status.
- No identifier fabricated for a report: `blocking` comes from the blueprint or
  is empty.
- No `KuzuClient` in flow code.
- No f-string containing a Cypher clause.
- No default value for an input whose absence is a configuration error.

## How to know the work is done

Delete `all_premature_specs` and the nine literal sections, and the module must
still produce the same gaps for the Nordwave engagement — because they now come
from `blueprints/BLU-hla-mcx.yaml`. If the gaps change, the blueprint does not
yet describe what the code used to assert, and it is the blueprint that needs
completing, not the code that needs its list back.
