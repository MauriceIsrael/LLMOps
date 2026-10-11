# Knowledge base proposals

Candidate payloads (`schemas/kb_candidate.schema.json`, one JSON object per line) waiting to be
submitted to the review queue. **They are not doctrine**: nothing here is served until a domain
owner reviews it through the candidate cycle.

| File | Content | Production mode |
|---|---|---|
| `it-infrastructure.jsonl` | IT infrastructure platform domain (plan L3 §6.3): 5 principles (P-016…P-020), 8 patterns (PAT-012…PAT-019), 5 ADRs (decision ids 0017 to 0021, not yet in `data/kb/decisions/`) covering bare metal, virtualization, container orchestration and PaaS | `llm-derived` — drafted by the coding agent |

Submit them to the queue (automatic checks run immediately, owners are notified):

```bash
poetry run kb submit data/proposals/it-infrastructure.jsonl
# or, against a running server: POST each line to /api/knowledge/candidates
```

Being `llm-derived`, they carry the `llm_unreviewed` warning and can only be published after a
human review (`review_kb_candidate` / the review inbox in Archinex (/kb/reviews)), then `kb promote` and
`kb publish`. Principles also require a second review.

## Framework ingestion proposals (`frameworks/`)

Proposals of links, acceptance criteria, search terms and French titles for requirements split
from an official source (`kb ingest-framework`), in the body format of
`POST /api/frameworks/ingestions/{id}/link-proposals`. They are **not** candidates: they annotate
the drafts of an ingestion as `llm-derived` and decide nothing until the expert accepts, amends or
rejects each row.

| File | Content | Production mode |
|---|---|---|
| `frameworks/NIS2-2022-2555.link-proposals.json` | The 9 NIS2 requirements without a control (Art. 20(1), 20(2), 21(1), 21(3), 21(4), 23(1)-(4)), from CELEX 32022L2555 | `llm-derived` — drafted by the coding agent |

```bash
# CLI: annotate the latest ingestion in data/staging, then build the review sheet
poetry run kb suggest-links --framework NIS2 --proposals data/proposals/frameworks/NIS2-2022-2555.link-proposals.json
poetry run kb review-sheet --framework NIS2
# API: POST the file as is to /api/frameworks/ingestions/{id}/link-proposals
```
