---
id: NIS2-ART21-2D
title: Sécurité de la chaîne d'approvisionnement et relations avec les fournisseurs
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [supply-chain,vendor-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-02
owner: security-compliance-team
---

# NIS2-ART21-2D — Sécurité de la chaîne d'approvisionnement et relations avec les fournisseurs

## Référence Réglementaire
Directive (UE) 2022/2555 (NIS 2), Article 21, Paragraphe 2, Point (d).

## Exigence Légale
Sécurité de la chaîne d'approvisionnement, y compris les aspects liés à la sécurité concernant les relations entre chaque entité et ses fournisseurs directs ou prestataires de services.

## Critères d'Acceptation d'Architecture
- Respect de la frontière éditeur : accès aux fonctions métier exclusivement via des API northbound documentées et contractées.
- Exigence d'évaluation des dépendances logicielles tierces et vérification des signatures d'artéfacts.
- Ségrégation stricte des flux techniques d'infogérance ou de télémaintenance éditeur.
