---
id: NIS2-ART21-2C
title: Continuité des activités, sauvegardes immuables et reprise après sinistre
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [resilience,disaster-recovery,backup-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# NIS2-ART21-2C — Continuité des activités, sauvegardes immuables et reprise après sinistre

## Référence Réglementaire
Directive (UE) 2022/2555 (NIS 2), Article 21, Paragraphe 2, Point (c).

## Exigence Légale
Gestion de la continuité des activités, telle que la gestion des sauvegardes et la reprise d'activité après sinistre, et gestion des crises.

## Critères d'Acceptation d'Architecture
- Architecture redondante active-active ou active-passive avec RTO et RPO formalisés et testés.
- Domaine de défaillance indépendant (procédure de break-glass et plan de repli lié à sa baseline).
- Sauvegardes immuables (WORM) isolées logiquement et physiquement du réseau principal.
