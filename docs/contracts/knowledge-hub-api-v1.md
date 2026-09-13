---
id: CONTRAT-KH-API-V1
title: Spécification Contractuelle de l'API Knowledge Hub (v1.0)
schemaVersion: "1.0"
status: active
owner: core-owner-llmops
last_reviewed: 2026-09-13
related: [ADR-SUITE-05, ADR-KH-01, ADR-DE-05, ADR-DS-07, TPL-third-party-integration-guide]
---

# Spécification Contractuelle de l'API Knowledge Hub (v1.0)

Ce document constitue le contrat d'interface formel, versionné et opposable entre le **Knowledge Hub (LLMOps)** et les composants consommateurs de l'Architecture Suite (`requirements-intake`, `document-studio`, `document-engine`, `WBS-engine`, ainsi que tout intégrateur tiers).

---

## 1. Architecture d'Intégration Dual-Mode

Le Knowledge Hub expose une architecture **Dual-Mode** permettant à chaque système consommateur de choisir son mode d'interaction selon ses contraintes d'isolation et de réseau :

```
                        ┌────────────────────────────────────────────────────────┐
                        │                 KNOWLEDGE HUB (LLMOps)                 │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                   ┌───────────────────────────────┴───────────────────────────────┐
                   ▼                                                               ▼
        [MODE 1 : Synchrone Direct]                                    [MODE 2 : Découplé / Scellé]
      (HTTP REST Request / Response)                                   (Instantanés JSON scellés SHA-256)
                   │                                                               │
    • Composants cibles :                                           • Composants cibles :
      - Document Studio (actions interactives à chaud)                - requirements-intake (sas d'admission local)
      - PetitesBriques (génération visuelle de canvas)                - document-engine (compilation pure hors-ligne)
      - Outils tiers, CLI et pipelines CI/CD                          - Enclaves souveraines / Air-Gapped (SecNumCloud)
```

1. **Mode 1 — Synchrone Interactif (HTTP REST direct)** :
   Le client interroge l'API du Hub en temps réel. Adapté pour les actions utilisateur interactives (demande de suggestion de prose, rafraîchissement d'un board de maturité, consultation des questions ouvertes).
2. **Mode 2 — Asynchrone Découplé (Instantanés Scellés & Curation Unifiée)** :
   Le client ingère ou produit des instantanés JSON immuables scellés par empreinte SHA-256 (conformes à `ADR-SUITE-05` et `ADR-KH-01`). Le sas d'admission local fonctionne de manière 100 % autonome (*offline-first*), sans dépendance réseau bloquante.

> [!IMPORTANT]
> **Contrat de Données Unifié** : Quel que soit le mode de transport (synchrone ou fichier scellé), les structures de données (`ExtractedCandidate`, `ConformitySnapshot`, `MaturityBoard`) respectent strictement les mêmes schémas canoniques.

---

## 2. Protocole, Authentification & Routage Multi-Bases

### 2.1 En-têtes Communs
* **Format de charge utile** : `Content-Type: application/json` (UTF-8 strict).
* **Authentification** : `Authorization: Bearer <LLMOPS_AUTH_TOKEN>`.
  *(Les routes `/health` et `/healthz` sont publiques et ne requièrent aucun jeton).*
* **Sélection d'engagement (Multi-Base)** :
  * Soit via l'en-tête HTTP : `X-Engagement-Id: <id-engagement>`
  * Soit via le paramètre d'URL : `?engagement=<id-engagement>`
  * Valeur par défaut si non spécifié : `"default"` (Socle transverse d'entreprise).

### 2.2 Politique d'Erreur & Résilience (« Fail Loud »)
Conformément aux conventions de robustesse de la suite, le Hub rejette le repli silencieux (*silent fallback*). En cas d'anomalie, le Hub retourne un code HTTP explicite accompagné d'un corps JSON structuré :
```json
{
  "status": "error",
  "error": "Description explicite et actionnable du diagnostic d'erreur"
}
```
* `400 Bad Request` : Paramètre manquant, JSON malformé ou non conforme au schéma.
* `401 Unauthorized` : Jeton absent, invalide ou insuffisant.
* `404 Not Found` : Engagement, ressource ou actif non trouvé.
* `500 Internal Server Error` : Défaillance interne du moteur ou de la base de graphe.

---

## 3. Registre des Canaux d'API

### 3.1 `GET /health` — Fiche d'Identité & Traçabilité (Double Versioning)
Retourne l'état de fonctionnement du Hub et scelle l'empreinte exacte du moteur et de la base de connaissances.
* **Accès** : Public (sans authentification).
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "plane": "all",
  "schema_version": "1.0",
  "service": "llmops-mcp-server",
  "engine_version": "0.1.0",
  "engine_commit": "474b9e3",
  "kb": {
    "snapshot_id": "snapshot-2026-09-13-fa1ecf2",
    "source_revision": "fa1ecf2b8be24ab7ccdea2cea6e1fd8d140ad485",
    "payload_sha256": "sha256:beb4c7cd2389cf7219871abba69f657e68562240d039e1fcf85ddb15b3068d7d",
    "created_at": "2026-09-13T14:40:46Z"
  }
}
```

---

### 3.2 `POST /api/rfp/shred-to-candidates` — Dépouillement CCTP & Export Candidats
Déstructure un texte de CCTP ou appel d'offres et projette les exigences extraites dans le format `ExtractedCandidate` (@architecture-suite/contracts).
* **Corps de requête** :
```json
{
  "rfp_text": "Le système complet doit être hébergé sur SecNumCloud 3.2...",
  "document_id": "cctp-2026-v1",
  "document_version": "1.0",
  "engagement": "default",
  "destination": "knowledge-hub-reference"
}
```
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "documentId": "cctp-2026-v1",
  "documentVersion": "1.0",
  "count": 14,
  "candidates": [
    {
      "id": "cand-REQ-SOUV-01",
      "sourceFragment": {
        "id": "frag-REQ-SOUV-01",
        "documentId": "cctp-2026-v1",
        "documentVersion": "1.0",
        "sectionPath": ["1.0"],
        "originalText": "Le système complet doit impérativement...",
        "hash": "sha256:4a8b..."
      },
      "originalText": "Le système complet doit impérativement...",
      "normalizedText": "Le système complet doit impérativement...",
      "candidateKind": "governance-obligation",
      "suggestedDestination": "knowledge-hub-reference",
      "routingConfidence": 0.95,
      "verificationModes": ["vendor-attestation", "manual-inspection"]
    }
  ]
}
```

---

### 3.3 `POST /api/elicitation/trigger` — Déclenchement Asynchrone d'Élicitation
Analyse les lacunes (gaps) d'un engagement et produit des questions ciblées de niveau L2 routées aux rôles d'experts.
* **Usage** : Déclenché out-of-band (à la demande de l'architecte ou via l'orchestrateur de build), sans couplage bloquant dans le sas d'admission.
* **Corps de requête** :
```json
{
  "engagement": "nordwave-mcx-2027"
}
```
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 3,
  "data": {
    "engagement": "nordwave-mcx-2027",
    "total_gaps_targeted": 3,
    "questions_created": 3,
    "questions": [
      {
        "id": "Q-RFP-011",
        "engagement": "nordwave-mcx-2027",
        "gap_type": "rfp_uncovered_requirement",
        "section": "4.0",
        "question": "Comment l'architecture doit-elle satisfaire l'exigence client : 'Interconnexion 3GPP MCX' ?",
        "why_it_matters": "Exigence mandatory du RFP non couverte par les motifs standards du Knowledge Hub.",
        "expected_shape": "Un énoncé technique précisant le composant ou la passerelle retenue.",
        "routed_to": "telco-specialist",
        "status": "open",
        "level": "L2_framed"
      }
    ]
  }
}
```

---

### 3.4 `GET /api/elicitation/questions` — Consultation des Questions Ouvertes
Liste les questions d'élicitation d'un engagement, avec filtrage optionnel par rôle d'expert.
* **Paramètres de requête** :
  * `role` *(optionnel)* : `lead-architect` | `security-architect` | `telco-specialist` | `compliance-lead` | `cloud-architect`
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 1,
  "data": [
    {
      "id": "Q-RFP-011",
      "routed_to": "telco-specialist",
      "question": "Comment l'architecture doit-elle satisfaire...",
      "status": "open",
      "level": "L2_framed"
    }
  ]
}
```

---

### 3.5 `GET /api/arbitration/board` — Tableau de Maturité d'Architecture (L0 à L4)
Expose la maturité d'ingénierie par sujet technique pour affichage direct dans Document Studio.
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 8,
  "data": [
    {
      "id": "mcx-services",
      "name": "Services Critiques MCX",
      "level": "L3_arbitrated",
      "is_stalled": false,
      "active_statements_count": 4,
      "open_conflicts_count": 0
    }
  ]
}
```

---

### 3.6 `GET /api/arbitration/conflicts` — Controverses et Conflits d'Architecture
Liste les contradictions détectées entre exigences ou entre choix d'architecture nécessitant un arbitrage humain.
* **Paramètres de requête** :
  * `status` *(optionnel)* : `open` | `resolved` | `waived` (défaut : `open`).
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 1,
  "data": [
    {
      "id": "CONF-001",
      "title": "Conflit Chiffrement mTLS vs Latence Floor Control (<100ms)",
      "status": "open",
      "statement_a_id": "STMT-001",
      "statement_b_id": "STMT-004",
      "suggested_arbitration": "Dérogation sur l'encapsulation SRTP directe pour les flux voix tactiques"
    }
  ]
}
```

---

### 3.7 `POST /api/knowledge/suggestions` — Boucle de REX et Curation Amont
Permet à Document Studio ou à un architecte de soumettre un motif éprouvé, un arbitrage ou une correction vers la gouvernance du Hub.
* **Corps de requête** :
```json
{
  "title": "Arbitrage HSM SecNumCloud : Partitionnement multi-tenant",
  "rationale": "Le CCTP impose une ségrégation stricte par opérateur.",
  "suggested_change": "Mettre à jour PAT-004 en recommandant des cartes dédiées...",
  "author": "lead-architect@entreprise.fr",
  "source_engagement": "nordwave-mcx-2027"
}
```
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "suggestion_id": "SUG-20260913-A8F4C2",
  "message": "Suggestion enregistrée avec succès pour revue de gouvernance."
}
```

---

### 3.8 `GET /api/compliance/conformity-snapshot` — Snapshot de Conformité Scellé
Produit un instantané réglementaire scellé par checksum SHA-256 calculé sur le profil strict `canonical-json (v1)`.
* **Paramètres de requête** :
  * `framework` : `SecNumCloud` | `ISO27001` | `NIS2` | `3GPP` | `ALL` (défaut : `ALL`).
  * `source_system` *(optionnel)* : `knowledge-hub` (défaut) | `tuleap` (rétrocompatibilité).
* **Réponse HTTP 200** :
```json
{
  "snapshotId": "kh-nordwave-mcx-2027-secnumcloud-1789311842",
  "sourceSystem": "knowledge-hub",
  "schemaVersion": "2.0",
  "createdAt": "2026-09-13T15:04:02Z",
  "checksum": "sha256:7a3c611095db2cd333cae158a715aea5dae6b55c381745c6423b1b5674313f4c",
  "data": {
    "requirements": [
      {
        "id": "SNC-REQ-01",
        "title": "Immunité aux lois extraterritoriales et localisation européenne des données",
        "domain": "SECURITY",
        "verificationModes": ["architecture-model"],
        "status": "verified",
        "evidence": [
          {
            "mode": "architecture-model",
            "type": "graph-item",
            "reference": "ADR-0011",
            "source": "architecture-studio"
          }
        ],
        "appliesTo": {
          "programRef": "NORDWAVE-MCX-2027",
          "lotRefs": [],
          "pbsRefs": []
        }
      }
    ]
  }
}
```

---

### 3.9 `GET /api/skills/matrix` — Matrice de Staffing & Risque WBS
Calcule l'adéquation entre les compétences requises par l'architecture du projet et les ressources mobilisées.
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 11,
  "data": {
    "engagement": "nordwave-mcx-2027",
    "coverage_percentage": 77.8,
    "risk_level": "moderate",
    "total_required_skills": 9,
    "covered_skills_count": 7,
    "missing_skills": ["SKL-CRYPTO-HSM", "SKL-MOB-FLEET"],
    "external_contractors": []
  }
}
```

---

## 4. Oracles & Vecteurs de Test Partagés

Afin de garantir une interopérabilité sans faille entre implémentations Python et TypeScript, les vecteurs de référence suivants sont tenus à disposition dans le dépôt :
* **Vecteur de Test Canonique (`canonical-json v1` + SHA-256)** : [`tests/fixtures/canonical_conformity_vector.json`](../../tests/fixtures/canonical_conformity_vector.json)
* **Jeu d'Essai CCTP de Référence (Messagerie OIV)** : [`fixtures/rfp_messagerie_securisee.txt`](../../fixtures/rfp_messagerie_securisee.txt) (SHA-256: `792b9d332e8ccc589a2d74468d56bc761539542fc8d337a71d77854f87c258b5`)

