# 3GPP Elicitation Benchmark Evaluation Protocol & Frozen Metrics

> **Protocol Status:** FROZEN  
> **Freeze Date:** 2026-08-27  
> **Rule 0.3 Invariant:** This protocol, its metrics, thresholds, and prompt templates are frozen prior to running model generation. Any post-freeze modifications must be explicitly dated and justified in this document.

---

## 1. Definition of an Architectural "Decision Point" (§2.1)

An architectural **Decision Point** is an architectural question that was open upon reading Stage 1 service requirements and receives an explicit structural choice in Stage 2 specifications.

### Criteria for Inclusion
To qualify as a Decision Point, an item MUST satisfy all three properties:
1. **Defendable Alternatives:** It represents a choice between at least two defendable architectural options (e.g. centralized vs distributed, unicast vs multicast, dedicated vs shared bearer).
2. **Textual Trace in Stage 2:** An explicit statement or structural decision resolving the choice is present in the Stage 2 specification.
3. **Structural System Impact:** The decision directly impacts system structure (entity responsibilities, interface boundaries, protocols, or state machines).

### Exclusions (What is NOT a Decision Point)
- Pure textual reformulations or paraphrasing of Stage 1 requirements.
- Stage 3 low-level bit/field protocol encoding details.
- Pure naming, term definition, or label choices.

---

## 2. Benchmark Metrics (§2.3, §4)

Because Stage 2 specifications do not answer every open architectural question raised by Stage 1, **Precision is explicitly prohibited as a benchmark metric**.

1. **Primary Metric — Decision Point Recall ($R$)**:
   $$\text{Recall} = \frac{|Q_{\text{generated}} \cap D_{\text{ground\_truth}}|}{|D_{\text{ground\_truth}}|}$$
   Percentage of ground-truth decision points covered by at least one generated question from the arm.

2. **Secondary Metric — Mean Reciprocal Rank (MRR)**:
   $$\text{MRR} = \frac{1}{|D|} \sum_{i=1}^{|D|} \frac{1}{\text{rank}_i}$$
   Measures question sequencing quality: the rank position of the first generated question that correctly matches ground-truth decision point $i$.

3. **Tertiary Metric — Un-Matched Question Classification**:
   For un-matched questions, a manual sample of 20 questions per arm is classified into three categories:
   - **Category 1 (Addressed Elsewhere):** Tranchée en Étape 3, autre spécification ou release ultérieure.
   - **Category 2 (Legitimately Open):** Question légitimement ouverte mais non tranchée par la norme 3GPP.
   - **Category 3 (Off-Topic / Irrelevant):** Hors sujet ou non pertinente.

4. **Exploratory Metric — Recall by Release Resolution Speed**:
   Recall broken down by the release where the decision was first resolved (Rel-13 immediate vs Rel-14+ multi-release resolution).

---

## 3. Pre-Defined Stop Criteria (§0.2)

1. **Stop Criterion 1 — Ill-defined task:** Inter-annotator (or test-retest) agreement $\kappa < 0.6$ on the double-annotated sample.
2. **Stop Criterion 2 — Insufficient gap:** Absolute recall advantage of Arm B over Arm A is less than 10 percentage points ($\Delta \text{Recall} < 0.10$).
3. **Stop Criterion 3 — Unacceptable contamination:** Baseline model reproduces Stage 2 architecture from memory without Stage 1 input.
