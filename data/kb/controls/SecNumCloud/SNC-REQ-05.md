---
id: SNC-REQ-05
title: Journalisation immuable et transmission en temps réel au SOC
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [observability,security-monitoring]
severity: mandatory
target_entities: [essential,critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# SNC-REQ-05 — Journalisation immuable et transmission en temps réel au SOC

## Référence Réglementaire
Référentiel d'exigences ANSSI SecNumCloud version 3.2, Exigence 12.4 (Surveillance, journalisation et détection).

## Exigence Légale
Les événements de sécurité, d'accès et d'administration doivent être journalisés sans délai, synchronisés sur une source de temps certifiée, scellés contre toute altération et analysés en temps réel par un SOC qualifié PDIS.

## Critères d'Acceptation d'Architecture
- Envoi chiffré et asynchrone des traces d'audit vers un puits de logs centralisé (SIEM/Elasticsearch) avec politique d'inviolabilité WORM (Write Once Read Many).
- Synchronisation des horloges sur au moins deux sources NTP sécurisées et signées.
- Détection proactive des anomalies de flux et déclenchement d'alertes automatiques vers l'équipe CSIRT/SOC.
