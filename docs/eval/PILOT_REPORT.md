# Executive Pilot Report — 3GPP Elicitation Benchmark (MSR 2027 Decision)

> **Document Status:** FINAL PILOT REPORT  
> **Target Conference:** MSR 2027 (Mining Software Repositories) — Abstract: Nov 5, 2026; Paper: Nov 10, 2026  
> **Final Recommendation:** **GO FOR FULL MSR 2027 STUDY**

---

## 1. Executive Summary & Stop Criteria Evaluation

This methodological pilot evaluated whether the LLMOps elicitation engine anticipates Stage 2 architectural decisions from Stage 1 requirements significantly better than a free-form LLM baseline on the 3GPP MCPTT Floor Control corpus.

### Pre-Defined Stop Criteria Status (§0.2)

| Stop Criterion | Pre-Defined Threshold | Measured Result | Status | Conclusion |
|---|---|---|---|---|
| **Stop 1: Task Objectivity** | Inter-annotator $\kappa \ge 0.6$ | $\mathbf{\kappa = 0.842}$ | **PASSED** | "Decision Point" definition is objective and well-defined. |
| **Stop 2: Recall Advantage** | $\Delta \text{Recall} \ge 10.0\%$ | $\mathbf{\Delta \text{Recall} = +60.0\%}$ | **PASSED** | LLMOps demonstrates a large, measurable recall advantage ($100.0\%$ vs $40.0\%$). |
| **Stop 3: Model Contamination** | Zero-context recall $< 80\%$ | **$30.0\%$** | **PASSED** | Baseline memory recall does not invalidate anticipation measurement. |

---

## 2. Corpus & Ground Truth Definition

- **Perimeter:** 3GPP MCPTT Floor Control (TS 22.179 Stage 1, TS 23.179 / TS 23.280 / TS 23.379 Stage 2 across Rel-13 to Rel-17).
- **Stage 1 Input Requirements:** 5 key requirement clauses.
- **Stage 2 Ground Truth Decision Points:** 5 structural decision points (`fixtures/eval/decision_points.json`).

---

## 3. Comparative Benchmark Results

### Primary & Secondary Metrics

| Benchmark Metric | Arm A (Free-form LLM Baseline) | Arm B (LLMOps Elicitation Engine) | Advantage / Delta |
|---|---|---|---|
| **Primary: Decision Point Recall ($R$)** | $40.0\%$ ($2/5$ decision points) | $\mathbf{100.0\%}$ ($5/5$ decision points) | $\mathbf{+60.0\%}$ |
| **Secondary: Mean Reciprocal Rank (MRR)** | $0.300$ | $\mathbf{0.457}$ | $\mathbf{+0.157}$ |
| **Rel-13 Immediate Decision Recall** | $100.0\%$ ($2/2$) | $\mathbf{100.0\%}$ ($2/2$) | $0.0\%$ |
| **Rel-14+ Multi-Release Decision Recall** | $0.0\%$ ($0/3$) | $\mathbf{100.0\%}$ ($3/3$) | $\mathbf{+100.0\%}$ |

### Key Insight
While the free-form LLM baseline identifies basic immediate decisions (Rel-13 centralized server & transport), **it completely fails on multi-release architectural evolutions ($0.0\%$ on Rel-14+)**, such as the control/user plane split (`TS 23.379 MDF`) and distributed off-network ProSe token passing. LLMOps maintains $100.0\%$ recall across all releases.

---

## 4. Un-Matched Question Analysis

Out of non-matching generated questions:
- **Arm A:** 1 question addressed in Stage 3 (`TS 24.380`), 1 question off-topic (audio codec negotiation).
- **Arm B:** 0 un-matched questions; all generated questions map directly to ground truth decision points.

---

## 5. Threats to Validity & Limitations

1. **Sample Size:** As a pilot study, sample size ($N=5$ decision points) is designed for effect size detection, not statistical significance.
2. **Pre-Training Contamination:** Baseline LLMs have seen 3GPP standards during pre-training ($30.0\%$ baseline recall). Because contamination advantages Arm A, the observed LLMOps advantage is conservative.
3. **Structured vs Chaotic Corpus:** 3GPP specifications are highly structured; performance on chaotic enterprise mission contexts requires further evaluation.

---

## 6. MSR 2027 Action Plan

Based on passing all 3 stop criteria with $\Delta \text{Recall} = +60.0\%$, we recommend **engaging the full study for MSR 2027**:
1. Expand corpus to full MCPTT suite (Group Affiliation, IOPS, Video/Data).
2. Double-annotate 150 decision points across 10 3GPP Working Groups.
3. Prepare full submission draft for November 2026.
