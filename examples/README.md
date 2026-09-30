# Examples — reference projects

The code in `mcp_server/`, `tools/` and `pipelines/` is generic: it names no project and holds
no project-specific rule (`make lint` runs `scripts/check_no_project_names.py`). Reference
projects live here and are **loaded at run time from data files**, never imported by the code.

| Path | Content |
|---|---|
| `nordwave-mcx-2027/` | Reference demo engagement (fictional mission-critical mobile network) |
| `nordwave-mcx-2027/scripted_interpretations.yaml` | Scripted interpretation of the demo answers (`ScriptedInterpreter`); any other engagement uses the `PassthroughInterpreter`, which invents no statement |
| `nordwave-mcx-2027/engagement_profile.yaml` | Engagement profile: default subject/role, question card vocabulary, instruction plan roster and sequence, harvest candidates |
| `nordwave-mcx-2027/petitesbriques_canvas.yaml` | PetitesBriques canvas template of the demo |
| `nordwave-mcx-2027/mailbox/`, `snapshots/`, `*.md` | Reference outputs of the demo scenario (question files, cards, documents, progression reports) |
| `nordwave-mcx-2027/reference-run/artifacts/` | Artefacts of a reference end-to-end run (cards, contributions, harvest, document) |
| `demo_knowledge_enrichment.py` | Script demonstrating the knowledge enrichment loop |

## Running the demo

```bash
make demo   # sets LLMOPS_ENGAGEMENT=nordwave-mcx-2027 and LLMOPS_BLUEPRINT=BLU-hla-mcx
```

The demo engagement database `data/engagements/nordwave-mcx-2027.lbug` stays versioned at the
same path (the public demo instance and the frozen interface fixtures depend on it); `make demo`
and the Dockerfile (re)publish it with the demo engagement configured through the environment.

The engine finds an engagement's example data in `$LLMOPS_EXAMPLES_DIR/<engagement>/`
(default `examples/`). Only the end-to-end tests (`tests/e2e/`) read `examples/`; unit and
contract tests use the synthetic data of `tests/fixtures/`.
