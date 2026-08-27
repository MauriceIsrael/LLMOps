# 3GPP Benchmark Corpus Specification (v2 Anti-Fabrication Protocol)

Per **Workorder v2 §4**, raw 3GPP PDF specifications remain un-tracked in `.gitignore`. Only SHA-256 hashes, file sizes, and extracted clause manifests are versioned under `docs/eval/SOURCES.md`.

---

## 1. Selected Functional Perimeter

- **Primary Functional Perimeter:** **MCPTT Floor Control** (Mission Critical Push To Talk over LTE).
- **Target Specifications:**
  - Stage 1: `TS 22.179` (Service Requirements)
  - Stage 2: `TS 23.179` (Rel-13 Initial Architecture), `TS 23.280` (Rel-14+ Common Architecture), `TS 23.379` (Rel-14+ MCPTT Architecture)

---

## 2. Source Documents Status & Hashing

| Document ID | Filename | SHA-256 Checksum | Extracted Length |
|---|---|---|---|
| **TS 22.179** | `TS_22.179.html` | `4df0b72be57ffd283415af450504985d5a342cebb187e52b73b96e88097263fc` | 1,719 chars |
| **TS 23.179** | `TS_23.179.html` | `75c26c1226b7e5397c4d800203ce20be36ed09b38225f212d6f45a15b65c2777` | 1,039 chars |
| **TS 23.280** | `TS_23.280.html` | `8469d07291fc1fe09acf9408050d98d36f9735f583e87d66248adce4afce290d` | 3,641 chars |
| **TS 23.379** | `TS_23.379.html` | `5b8db2a860e5efa2fa2d97313dc6481499b599f6b92c91db5438485456708e8e` | 3,518 chars |

---

## 3. Candidate Annotation File

The candidate clauses have been extracted into `annotation/candidates.csv`. The three annotation columns (`is_decision_point`, `question`, `verbatim`) are strictly empty for human annotation.
