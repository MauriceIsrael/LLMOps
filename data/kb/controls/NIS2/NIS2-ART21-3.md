---
id: NIS2-ART21-3
title: Supply chain security and supplier-specific vulnerability assessment
type: control
framework: NIS2
version: 2022/2555
jurisdiction: EU
domain: [security-governance]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: '2026-11-16'
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(3)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:04Z'
revision: 2
title_fr: 'Chaîne d''approvisionnement : vulnérabilités propres à chaque fournisseur'
terms: [supplier assessment, third-party risk, sbom, évaluation des fournisseurs, risque fournisseur, chaîne d'approvisionnement]
satisfied_by: [PAT-023]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART21-3 — Supply chain security and supplier-specific vulnerability assessment

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21(3).

## Legal Requirement
Member States shall ensure that, when considering which measures referred to in paragraph 2, point (d), of this Article are appropriate, entities take into account the vulnerabilities specific to each direct supplier and service provider and the overall quality of products and cybersecurity practices of their suppliers and service providers, including their secure development procedures. Member States shall also ensure that, when considering which measures referred to in that point are appropriate, entities are required to take into account the results of the coordinated security risk assessments of critical supply chains carried out in accordance with Article 22(1).

## Architecture Acceptance Criteria
- Each direct supplier and service provider of the architecture (hardware, software, cloud, managed services) is listed with an assessment of its specific vulnerabilities, product quality and secure development practices.
- Supplier selection takes into account the results of the EU coordinated security risk assessments of critical supply chains (Article 22(1)) when they apply to the components chosen.
- Contracts with suppliers require vulnerability notification, security updates over the support period and, for software, a software bill of materials.