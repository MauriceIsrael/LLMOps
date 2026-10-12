---
id: NIS2-ART21-2C
title: Business Continuity and Crisis Management
title_fr: Continuité des activités et gestion de crise
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [business-continuity, disaster-recovery]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(c)
terms: [break-glass, fallback-plan, immutable-log]
# Draft check clauses proposed by the coding agent (regulatory frameworks) — NOT validated.
# To be accepted, amended or rejected by the domain expert through the KB review cycle (L2).
checks_status: draft
checks:
- id: NIS2-ART21-2C-C1
  kind: forbids
  when:
    terms_any: [no backup, without backup, no disaster recovery, without disaster recovery, no failover, single site with no failover, sans sauvegarde, aucune sauvegarde, pas de sauvegarde, sans plan de reprise, pas de plan de reprise, sans reprise d'activite, backups on the same storage as production, backups in the same data centre as production, sauvegardes sur le meme stockage que la production, sauvegardes dans le meme datacenter que la production]
  message: 'NIS2 Art. 21(2)(c): business continuity needs backups and a disaster recovery capability kept apart from the production failure domain.'
- id: NIS2-ART21-2C-C2
  kind: requires
  when:
    terms_any: [backup solution, backup strategy, backup policy, backup copies, data backup, backup server, disaster recovery, business continuity plan, solution de sauvegarde, strategie de sauvegarde, politique de sauvegarde, sauvegarde des donnees, plan de reprise, plan de continuite d'activite]
  expect:
    terms_any: [immutable, immuable, worm, offline copy, offline backup, copie hors ligne, sauvegarde hors ligne, air-gapped, air gap, off-site, offsite, hors site, second site, secondary site, site secondaire, second data centre, second datacenter, second region, separate region, autre region, second data center, two data centres, two data centers, two sites, multi-site, multi-region, active-active, geo-redundant, deux datacenters, deux centres de donnees, deux sites, georedondant, restore test, restoration test, test de restauration, tests de restauration, rpo, rto]
  message: 'NIS2 Art. 21(2)(c): backups and disaster recovery must be segregated (off-site, offline or immutable copies) with recovery objectives and tested restores.'
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:57Z'
revision: 2
---

# NIS2-ART21-2C — Business Continuity and Crisis Management

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (c).

## Legal Requirement
Business continuity, such as backup management and disaster recovery, and crisis management.

## Architecture Acceptance Criteria
- Redundant active/passive deployment topology across distinct availability zones.
- Independent failure domain with documented break-glass procedures and baseline-bound fallback plans.
- Immutable, write-once-read-many (WORM) backups logically and physically segregated from the primary network.
