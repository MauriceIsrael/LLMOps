# 3GPP Benchmark Corpus Specification (v2 Anti-Fabrication Protocol)

Per **Workorder v2 §4.1**, raw 3GPP specifications remain un-tracked in `.gitignore`.
Only SHA-256 hashes, file sizes, and extracted clause manifests are versioned under `docs/eval/SOURCES.md`.

---

## 1. Selected Functional Perimeter & Perimeter Count Check (§4.1)

- **Primary Selected Perimeter:** **MCPTT Floor Control** (Mission Critical Push To Talk over LTE).
- **Stage 2 Floor Control Clause Count:** **62 substantial clauses** across `TS 23.179`, `TS 23.280`, and `TS 23.379`.
- **Stage 3 Floor Control Clause Count:** **101 substantial clauses** in `TS 24.380`.
- **Perimeter Threshold Decision (§4.1):** Stage 2 offers **62 clauses** (minimum threshold is $\ge 10$). **Perimeter is validated and retained.**

---

## 2. Version Pairing & Document Status

| Stage | Document ID | Version | Description & Role | SHA-256 Checksum | Extracted Text Volume |
|---|---|---|---|---|---|
| **Stage 1 (Input)** | `TS 22.179` | `v13.3.0` (`22179-d30`) | Rel-13 Service Requirements | `5948f9b489af82572b6c9b31d06e23298ec6971936c53e05a3e1eb5272a58b52` | 233,237 chars |
| **Stage 2 (Base)** | `TS 23.179` | `v13.5.0` (`23179-d50`) | Rel-13 Frozen Architecture | `f2c68686e84eb141590ce49ebacf8587fea1094d485d8183b077c963418bd93e` | 573,686 chars |
| **Stage 2 (Common)**| `TS 23.280` | `v14.4.0` (`23280-k40`) | Rel-14+ Common Architecture | `cae67670b311a2a776646c14d0cbdd7dbe0951dbd999a987f2e96f4ea3b99e43` | 820,983 chars |
| **Stage 2 (MCPTT)** | `TS 23.379` | `v14.3.0` (`23379-k30`) | Rel-14+ MCPTT Architecture | `7da40c6dcab4913ddd31d7d39cb51119731ae9ef1319030eaa2d7ca105447629` | 535,983 chars |
| **Stage 3 (Protocol)**| `TS 24.380` | `v14.0.0` (`24380-k00`) | Rel-14+ MCPTT Protocol | `303ddcbfdd795fb8f732ca4c668be55d34f550d5f57eea63b04fa557c43428d1` | 744,994 chars |

---

## 3. Candidate Annotation CSV Status

Candidate clauses have been exported to `annotation/candidates.csv`. The three annotation columns (`is_decision_point`, `question`, `verbatim`) are strictly empty for human annotation.
