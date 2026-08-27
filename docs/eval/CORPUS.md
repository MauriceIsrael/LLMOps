# 3GPP Benchmark Corpus Definition & Filtering Report

This document defines the functional perimeter, specification documents, releases, and clause filtering criteria for the LLMOps 3GPP benchmark pilot.

Per **Rule 0.3 #4**, raw specification texts are not stored in the repository. Only stable 3GPP references (specification number, release, version, clause ID) and derived annotations are versioned under `fixtures/eval/corpus_clauses.json`.

---

## 1. Functional Perimeter

- **Primary Selected Perimeter:** **MCPTT Floor Control** (Mission Critical Push To Talk over LTE).
- **Justification:** Narrow, well-demarcated functional perimeter with explicit Stage 1 service requirements, explicit Stage 2 architectural entities/procedures, and a multi-release evolution history (Rel-13 through Rel-17).

---

## 2. Target Specifications & Depth

| Stage | Document ID | Title | Releases Included | Role in Benchmark |
|---|---|---|---|---|
| **Stage 1** | `TS 22.179` | Mission Critical Push To Talk (MCPTT) over LTE; Service requirements | Rel-13, Rel-14, Rel-15, Rel-16, Rel-17 | **Benchmark Input** (Supplied to both Arm A and Arm B) |
| **Stage 2** | `TS 23.179` | Functional architecture and information flows to support MCPTT (Rel-13 initial) | Rel-13 | **Ground Truth Baseline** (Initial joint architecture) |
| **Stage 2** | `TS 23.280` | Common functional architecture for mission critical services (Rel-14+) | Rel-14, Rel-15, Rel-16, Rel-17 | **Ground Truth Baseline** (Split common architecture) |
| **Stage 2** | `TS 23.379` | Mission Critical Push To Talk (MCPTT) media plane control (Rel-14+) | Rel-14, Rel-15, Rel-16, Rel-17 | **Ground Truth Baseline** (Split MCPTT architecture) |
| *Stage 3* | `TS 24.380` | MCPTT Floor Control Protocol | *Excluded* | Informational only; excluded from ground truth per §2.3. |

---

## 3. Retained Clause Volume & Filtering Criteria

- **Filtering Keyword Criteria:** Clauses tagged under topic `floor_control` referencing floor request, floor grant, floor preemption, floor revoking, floor queueing, and off-network ProSe floor arbitration.
- **Indexed Volume (`fixtures/eval/corpus_clauses.json`):**
  - **Stage 1 Requirement Clauses:** 5 key requirement clauses.
  - **Stage 2 Decision Points:** 5 architectural decision points across Rel-13, Rel-14, and Rel-15.

---

## 4. Architectural Evolution Note

The structural decomposition of `TS 23.179` (Rel-13 single document) into `TS 23.280` (Common Architecture) and `TS 23.379` (MCPTT Media/Floor Plane) in Rel-14 represents a major, traceable architectural decision. This evolution is retained in the evaluation perimeter.
