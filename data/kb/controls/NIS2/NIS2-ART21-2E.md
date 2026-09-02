---
id: NIS2-ART21-2E
title: Sécurité de l'acquisition, du développement et de la maintenance des SI
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [secure-development,vulnerability-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# NIS2-ART21-2E — Sécurité de l'acquisition, du développement et de la maintenance des SI

## Référence Réglementaire
Directive (UE) 2022/2555 (NIS 2), Article 21, Paragraphe 2, Point (e).

## Exigence Légale
Sécurité de l'acquisition, du développement et de la maintenance des réseaux et des systèmes d'information, y compris le traitement et la divulgation des vulnérabilités.

## Critères d'Acceptation d'Architecture
- Validation en environnement fantôme (shadow validation) avant tout armement ou passage en production.
- Gestion continue du cycle de vie des vulnérabilités avec délai de remédiation borné selon la criticité.
- Intégration de portes de sécurité (security gates) dans les pipelines de déploiement continu.
