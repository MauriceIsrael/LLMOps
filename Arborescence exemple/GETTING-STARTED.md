---
id: TPL-getting-started
title: Getting started — publishing and collaborating on this base
type: template
status: active
confidence: verified
phase: [BID, BUILD, RUN]
domain: [delivery]
owner: maintainers
last_reviewed: 2026-07-25
---

# Getting started

## 1. Publish it on GitHub

The repository is already initialized with one commit on `main`. Two ways to
push it to your account.

**With the GitHub CLI** (creates the remote repository and pushes in one step):

```bash
cd architecture-kb
gh auth login                       # once per machine
gh repo create <org-or-user>/architecture-kb \
    --private --source=. --remote=origin --push
```

**Without the CLI** — create an empty repository on github.com first (no README,
no .gitignore, no licence), then:

```bash
cd architecture-kb
git remote add origin git@github.com:<org-or-user>/architecture-kb.git
git push -u origin main
```

Use SSH (`git@github.com:`) rather than HTTPS if your organization requires it;
otherwise `https://github.com/<org-or-user>/architecture-kb.git` works with a
personal access token.

If the repository was initialized before you had `git` configured, set the
authorship on the first commit:

```bash
git config user.name  "Your Name"
git config user.email "you@company.com"
git commit --amend --reset-author --no-edit
git push -u origin main --force-with-lease   # only safe before anyone cloned
```

## 2. Protect the main branch

Do this before inviting anyone. On GitHub: **Settings → Rules → Rulesets → New
branch ruleset**, target `main`, and enable:

- Require a pull request before merging, with **1 approval**.
- Require review from **Code Owners** (this activates the `CODEOWNERS` file).
- Require status checks to pass: select the `validate` workflow.
- Block force pushes.

Without this, `CODEOWNERS` is decorative and the front-matter validation is
advisory. With it, the governance described in `GOVERNANCE.md` is enforced by
the platform rather than by goodwill.

Then replace the placeholder handles in `CODEOWNERS` with real GitHub usernames
or teams, and commit that as your second change — through a pull request, to
prove the flow works.

## 3. Onboard a colleague

```bash
git clone git@github.com:<org-or-user>/architecture-kb.git
cd architecture-kb
pip install pyyaml jsonschema
python schema/validate.py           # should print 0 errors
```

Then read `CONTRIBUTING.md`. It is two pages and it answers the only question a
new contributor has: *what goes where, and when.*

## 4. The everyday loop

```bash
git switch main && git pull
git switch -c adr/0014-transport-vendor-selection

# write the asset, copying the closest existing one rather than the template
cp decisions/ADR-0006.md decisions/ADR-0014.md
$EDITOR decisions/ADR-0014.md

python schema/validate.py
git add decisions/ADR-0014.md
git commit -m "ADR-0014: transport vendor selection"
git push -u origin adr/0014-transport-vendor-selection
gh pr create --fill                 # or open it in the web interface
```

Branch prefixes: `adr/`, `pat/`, `principle/`, `qst/`, `est/`, `risk/`, `view/`,
`project/<name>/`, `harvest/<engagement>-<phase>`.

Commit messages start with the asset identifier. That is the whole convention —
`git log --oneline decisions/` then reads as a decision history.

## 5. Keeping identifiers unique

Identifiers are allocated by taking the next free number **on `main`**, not on
your branch. Two people drafting `ADR-0014` simultaneously is the one collision
this base can suffer, and `python schema/validate.py` catches it at review time.
For a team larger than five, open the "Decision needed" issue first: the issue
number reserves the slot and gives the decision a place to be discussed before
it is written.

## 6. What good contribution looks like

The base fails in one of two ways, and both are avoidable.

**It fills with drafts nobody promoted.** Prevention: `draft` assets older than
two harvests are deleted, and CI warns you before that. Write fewer, finished
assets.

**It becomes an archive nobody trusts.** Prevention: the harvest. Create the
harvest issue at phase kickoff, not at phase end — an obligation that appears at
the end is an obligation that is skipped. The single most valuable contribution
anyone makes to this base is the `actuals` line in an estimate and the
`materialized_in` line in a risk register, because those are the two things no
amount of architecture thinking can produce.

## 7. Wiring the agents

Implement the server described in `mcp/SPEC.md` against a clone of this
repository, and give it read-only credentials. Agents draft through pull
requests and never push. When you add the server to your agent framework, add
the prompt fragment at the end of the specification: it is what makes an agent
state the confidence level of what it asserts instead of flattening your
assumptions into facts.
