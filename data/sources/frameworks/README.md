# Official sources of the regulatory frameworks

Source documents ingested with `kb ingest-framework` (plan L3 §6.1, L8). The SHA-256 of each
file is the `source_sha256` recorded in `data/kb/controls/<FW>/_manifest.yaml` and in every
control promoted from the ingestion: a coverage declaration only survives while the source and
the version are unchanged.

Texts of the Official Journal of the European Union published on EUR-Lex may be reused
(Commission Decision 2011/833/EU); only the Official Journal edition is authentic. Paid standards
(ISO/IEC 27001, ISO 22301, ...) are **never** stored here: their text is licensed.

| Framework | Act | File | SHA-256 | Retrieved |
|---|---|---|---|---|
| NIS2 | Directive (EU) 2022/2555 — CELEX 32022L2555 | `NIS2/CELEX_32022L2555_EN.html` | `c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b` | 2026-10-11 |
| RGPD | Regulation (EU) 2016/679 (GDPR) — CELEX 32016R0679 | `RGPD/CELEX_32016R0679_EN.html` | `1eb90b1afc2193007125febb9dbabe0c110cbb93aee17d16ac869317a1b814be` | 2026-10-11 |
| CRA | Regulation (EU) 2024/2847 (Cyber Resilience Act) — CELEX 32024R2847 | `CRA/CELEX_32024R2847_EN.html` | `3551fbf856d2e65ffc445a87ede903f0da097e27edddf1f1a781597ef0396302` | 2026-10-11 |

## Re-fetching

```bash
curl -sSL -o data/sources/frameworks/NIS2/CELEX_32022L2555_EN.html \
  "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022L2555"
curl -sSL -o data/sources/frameworks/RGPD/CELEX_32016R0679_EN.html \
  "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679"
curl -sSL -o data/sources/frameworks/CRA/CELEX_32024R2847_EN.html \
  "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32024R2847"
sha256sum data/sources/frameworks/*/*.html
```

EUR-Lex regenerates its HTML from time to time (the `generated_on` comment at the top of the
file): the legal text may be identical while the SHA-256 differs. A new hash means a new source
for the manifest, so the expert reviews the ingestion again before declaring coverage.

## Ingesting

```bash
poetry run kb ingest-framework --framework NIS2 --version 2022/2555 --source data/sources/frameworks/NIS2/CELEX_32022L2555_EN.html
poetry run kb ingest-framework --framework RGPD --version 2016/679 --source data/sources/frameworks/RGPD/CELEX_32016R0679_EN.html
poetry run kb ingest-framework --framework CRA --version 2024/2847 --source data/sources/frameworks/CRA/CELEX_32024R2847_EN.html
```

The splitters are in `pipelines/frameworks/splitters/` (`nis2.yaml`, `rgpd.yaml`, `cra.yaml`);
the drafts land in `data/staging/<FW>/<version>/` (ignored by git), then go through
`kb suggest-links`, `kb review-sheet` and `kb apply-review` (or the `/api/frameworks/ingestions`
routes). Through the API, upload the same file to `POST /api/frameworks/ingestions`.
