---
id: SNC-REQ-06
title: Résilience multi-sites et plans de continuité d'activité (PCA/PRA)
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [resilience,business-continuity]
severity: mandatory
target_entities: [essential,critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# SNC-REQ-06 — Résilience multi-sites et continuité d'activité

## Référence Réglementaire
Référentiel d'exigences ANSSI SecNumCloud version 3.2, Exigence 17.1 (Continuité d'activité et reprise après sinistre).

## Exigence Légale
Le service doit être déployé de façon redondante sur plusieurs zones de disponibilité distinctes non soumises aux mêmes risques physiques. Les procédures de bascule doivent être automatisées et testées au moins une fois par an.

## Critères d'Acceptation d'Architecture
- Déploiement actif/actif ou actif/veille sur au moins deux sites géographiquement distants (> 30 km).
- RPO = 0 pour les flux transactionnels critiques et RTO < 60 secondes pour les services prioritaires de voix et signalisation MCX.
- Automatisation des scénarios de bascule de réseau WAN et vérification de la non-dépendance à un point unique de défaillance (Single Point of Failure).
