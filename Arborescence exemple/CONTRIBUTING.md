# Contributing — what goes where, and when

This is the operating manual for architects. It is deliberately short: if a rule
needs a paragraph of explanation, it is the wrong rule.

## 1. The decision tree

Ask one question: **what kind of thing did I just produce?**

| I have just... | It goes in | Identifier |
|---|---|---|
| made a choice where credible alternatives existed | `decisions/` | `ADR-nnnn` |
| written a rule that will constrain future choices | `principles/` | `P-nnn` |
| solved a problem in a way I would repeat | `patterns/` | `PAT-nnn` |
| found a question I wish I had asked a vendor earlier | `questionnaires/` | existing `QST-xxx` |
| learned what something actually cost | `estimates/` | existing `EST-xxx` |
| been bitten by something foreseeable | `risks/` | existing `RSK-xxx` |
| produced a diagram I will need again | `views/generators/` | generator script |
| agreed something with one client only | `projects/<engagement>/` | project instance |

If none fits, it is probably **project context** and belongs in
`projects/<engagement>/`, not in the reusable core.

## 2. The promotion rule

Nothing enters the reusable core straight from an engagement.

- **First occurrence** → it lives in `projects/<engagement>/`.
- **Second occurrence, different engagement** → open a promotion pull request
  moving the generalized form into `patterns/` or `decisions/`, stripped of any
  client-identifying material.
- **A principle** is only added when it has already constrained at least two
  decisions. Principles that never constrained anything are opinions.

This rule exists to keep the core small enough to be read.

## 3. When to write, by phase

**BID.** Write the *claims register* first (`templates/claims-register.md`) — it
forces every statement in the proposal to carry an evidence level. Record as
ADRs the choices you make to build the response, even provisional ones: mark
them `status: proposed`. Open questions to vendors go into the project instance
as unanswered questionnaire items, never as assumptions dressed as facts.

**BUILD.** Write ADRs *as you decide*, not afterwards. An ADR written three
months later is an invented rationalization. Record the vendor answers in the
project's questionnaire file as they arrive; a `pending` answer that stays
pending for a month is a risk, and should be raised as one.

**RUN.** This is where the base earns its keep and where contribution usually
stops. Record what actually happened: measured effort against the estimate,
which automation graduated to higher autonomy and after how long, what went
stale, what was never used. Do this at the harvest (see below), not
continuously.

## 4. The harvest

At the end of each phase, one session, timeboxed, with the engagement architect
and one core owner. Output is a single pull request that:

1. updates `estimates/` with actuals and, if needed, the variance drivers;
2. updates `risks/` with what materialized and what never did;
3. amends or supersedes ADRs whose consequences turned out differently;
4. promotes anything that has now occurred twice;
5. **deprecates** what is no longer true.

An open harvest issue is created from `.github/ISSUE_TEMPLATE/harvest.md` at
phase kickoff, so the obligation is visible from the start rather than
remembered at the end.

## 5. Writing rules

- One asset, one file. No omnibus documents.
- Front matter is mandatory and validated by CI.
- `confidence:` is not decoration. Use `verified` only for something you or a
  colleague observed directly; `vendor-stated` for documentation and vendor
  claims; `assumed` for anything else. An agent will restate your assumptions
  with the same assurance as your facts unless you mark them.
- Write the *why*, not only the *what*. A decision without its rejected
  alternatives is worthless in two years.
- Never delete an asset. Set `status: superseded` and link the successor.

## 6. Pull request flow

```bash
git switch -c adr/0014-transport-vendor-selection
# write the asset
python schema/validate.py            # same check CI runs
git add . && git commit -m "ADR-0014: transport vendor selection"
git push -u origin adr/0014-transport-vendor-selection
```

Then open a pull request using the template. Branch naming:
`adr/`, `pat/`, `principle/`, `qst/`, `est/`, `risk/`, `view/`, `project/<name>/`,
`harvest/<engagement>-<phase>`.

Review requirements are in `CODEOWNERS`: one core owner for anything in the
reusable core, engagement architect only for `projects/`.

## 7. Agents

Agents read this base through the server specified in `mcp/SPEC.md`. They may
**draft** assets and open pull requests; they may never push to `main`. A pull
request opened by an agent is labelled `agent-drafted` and requires the same
human review as any other — plus an explicit check that the `confidence` field
was not inflated.
