# Governance

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Core owner | One named architect per domain (network automation, observability, cloud platform, service management, AI assistance) | Reviews changes to the reusable core in their domain; arbitrates promotions |
| Engagement architect | Lead architect of a client engagement | Owns `projects/<engagement>/`; runs the harvest |
| Maintainer | 1–2 people | Repository hygiene, CI, schema evolution, release tagging |

Owners are declared in `CODEOWNERS`. A domain without a named owner is a domain
whose assets will rot; if an owner leaves, reassign before the next harvest.

## Maturity and status

Every asset carries `status` and `confidence`.

`status`: `draft` → `active` → `superseded` | `deprecated`
`confidence`: `verified` | `vendor-stated` | `assumed`

Only `active` assets are served to agents by default. `draft` assets are visible
to humans and must be either promoted or dropped at the next harvest — a `draft`
older than two harvests is deleted, because a permanently draft asset is noise.

## Review cadence

- **Continuous**: pull requests, reviewed within five working days.
- **Per phase**: the harvest (see `CONTRIBUTING.md`).
- **Twice yearly**: core review. Owners walk their domain, check `last_reviewed`
  dates, deprecate what no longer holds, and re-verify `vendor-stated` items
  against current vendor documentation. Vendor capabilities move fast; an
  unreviewed `vendor-stated` assertion older than twelve months is downgraded to
  `assumed` automatically by CI.

## Confidentiality

`projects/` may contain client-identifying material and is subject to the
engagement's confidentiality terms. The reusable core must not. Promotion out of
a project instance requires removing client names, site names, addressing plans,
volumes and commercial terms. When in doubt, generalize harder — the value of a
pattern is in its structure, not in whose network it came from.

## Releases

Tag `main` at each core review (`v<year>.<n>`). Proposals and dossiers cite the
tag they were generated from, so a two-year-old proposal can be reconstructed
exactly.
