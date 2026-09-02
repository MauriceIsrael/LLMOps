---
id: NIS2-ART21-2H
title: Cryptographie, chiffrement et sécurité de l'intelligence artificielle
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [cryptography,ai-security]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# NIS2-ART21-2H — Cryptographie, chiffrement et sécurité de l'intelligence artificielle

## Référence Réglementaire
Directive (UE) 2022/2555 (NIS 2), Article 21, Paragraphe 2, Point (h).

## Exigence Légale
Politiques et procédures relatives à l'utilisation de la cryptographie et, le cas échéant, au chiffrement.

## Critères d'Acceptation d'Architecture
- Chiffrement systématique des données en transit (mTLS) et au repos (clés ségréguées sous contrôle client).
- Modèle d'intelligence artificielle maintenu dans la frontière de confiance (pas d'exfiltration de contexte).
- L'assistant conseille mais n'agit pas directement : outillage en mode préparation seule.
