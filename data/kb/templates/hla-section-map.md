---
id: TPL-hla-section-map
title: Mapping of knowledge assets to the high-level architecture blueprint
type: template
status: active
confidence: verified
phase: [BID]
domain: [delivery]
owner: core-owner-architecture
last_reviewed: 2026-07-25
---

# HLA section map

Where each asset type lands when generating a high-level architecture document
from this base. Used by the agent that drafts a proposal instance.

| Blueprint section | Assets to inject |
|---|---|
| 1.2 Scope and boundaries | Project scope statement, ADR-0005, ADR-0013 |
| 1.4 Vision and guiding principles | All active principles, rendered as a table |
| 3.3 Data governance and sovereignty | P-015, security section of the project instance |
| 4.2 Interoperability and external integration | ADR-0005, ADR-0009, PAT-006 |
| 4.4 SIM and eSIM lifecycle | ADR-0013, QST-service-management answers |
| 5.2 Compute and cloud platform | ADR-0006, ADR-0007, hosting and physical views |
| 5.2.1 Multi-environment staging | ADR-0012, PAT-002, lambda view |
| 6.3 Graceful degradation | P-009, PAT-004 |
| 7.1–7.4 Security and compliance | P-002, P-007, P-012, P-015, PAT-004 |
| 8.1 Operational vision | Conceptual view, P-004, ADR-0008 |
| 8.2–8.3 Assistant in BUILD and RUN | PAT-007, ADR-0011, assistant view |
| 8.4 Source of truth and automation chain | P-001, functional and deployment views |
| 8.5 Supervised governance | PAT-001, P-002, P-003, P-004 |
| 8.6 Service management and audit | ADR-0009, P-010 |
| 9.1 Software stack | Software view, component table from the project instance |
| 10.4 Delivery roadmap | EST-netdevops-telco |
| 10.5 Risk mitigation | RSK-netdevops-telco |
| Appendix A traceability | Generated from the mapping above |
| Appendices B–D | The three questionnaires |
