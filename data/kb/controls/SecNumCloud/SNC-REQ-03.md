---
id: SNC-REQ-03
title: Gestion des clés cryptographiques sur HSM qualifié ANSSI
type: control
framework: SecNumCloud
version: "3.2"
jurisdiction: FR-EU
domain: [cryptography,data-protection]
severity: mandatory
target_entities: [essential,critical-infrastructure]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# SNC-REQ-03 — Gestion des clés cryptographiques sur HSM qualifié ANSSI

## Référence Réglementaire
Référentiel d'exigences ANSSI SecNumCloud version 3.2, Exigence 10.1 (Cryptographie et gestion des clés).

## Exigence Légale
Toutes les clés maîtresses de chiffrement au repos et de signature doivent être générées et conservées dans un module matériel de sécurité (HSM) ayant obtenu une qualification ANSSI (niveau standard ou renforcé).

## Critères d'Acceptation d'Architecture
- Intégration d'un HSM physique qualifié ANSSI pour la racine de confiance (Root of Trust) et les clés KMS MCX.
- Chiffrement enveloppe (Envelope Encryption) avec rotation automatisée et contrôlée des clés de chiffrement de données (DEK).
- Séparation stricte des rôles entre administrateurs de l'infrastructure et dépositaires des secrets cryptographiques.
