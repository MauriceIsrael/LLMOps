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
human review (`review_kb_candidate` / the /governance/candidates screen), then `kb promote` and
`kb publish`. Principles also require a second review.
