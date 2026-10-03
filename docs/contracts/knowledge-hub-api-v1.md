---
id: CONTRAT-KH-API-V1
title: Spécification Contractuelle de l'API Knowledge Hub (v1.0)
schemaVersion: "1.0"
status: active
owner: core-owner-llmops
last_reviewed: 2026-09-27
related: [ADR-0015, ADR-SUITE-05, ADR-KH-01, ADR-DE-05, ADR-DS-07, TPL-third-party-integration-guide]
---

# Spécification Contractuelle de l'API Knowledge Hub (v1.0)

Ce document constitue le contrat d'interface formel, versionné et opposable entre le **Knowledge Hub (LLMOps)** et les composants consommateurs de l'Architecture Suite (`requirements-intake`, `document-studio`, `document-engine`, `WBS-engine`, ainsi que tout intégrateur tiers comme `Archinex`).

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
      - Archinex Cockpit (Mode connecté FastMCP / REST)               - document-engine (compilation pure hors-ligne)
      - Outils tiers, CLI et pipelines CI/CD                          - Archinex Cockpit (Mode déconnecté / Air-Gapped)
                                                                       - Enclaves souveraines (SecNumCloud)
```

1. **Mode 1 — Synchrone Interactif (HTTP REST direct & FastMCP SSE)** :
   Le client interroge l'API du Hub en temps réel. Adapté pour les actions utilisateur interactives (demande de suggestion de prose, rafraîchissement d'un board de maturité, consultation des questions ouvertes).
2. **Mode 2 — Asynchrone Découplé (Instantanés Scellés & Curation Unifiée)** :
   Le client ingère ou produit des instantanés JSON immuables scellés par empreinte SHA-256 (conformes à `ADR-SUITE-05`, `ADR-KH-01` et `ADR-0015`). Le sas d'admission local fonctionne de manière 100 % autonome (*offline-first*), sans dépendance réseau bloquante.

> [!IMPORTANT]
> **Contrat de Données Unifié** : Quel que soit le mode de transport (synchrone ou fichier scellé), les structures de données (`ExtractedCandidate`, `ConformitySnapshot`, `MaturityBoard`) respectent strictement les mêmes schémas canoniques.

---

## 2. Protocole, Authentification & Routage Multi-Bases

### 2.1 En-têtes Communs & Isolation Physique (ADR-0015)
* **Format de charge utile** : `Content-Type: application/json` (UTF-8 strict).
* **Authentification** : `Authorization: Bearer <LLMOPS_AUTH_TOKEN>`.
  *(Les routes `/health`, `/healthz`, `/ready` et `/readyz` sont publiques et ne requièrent aucun jeton).*
* **Sélection d'engagement (Multi-Base)** :
  * Soit via l'en-tête HTTP : `X-Engagement-Id: <id-engagement>`
  * Soit via le paramètre d'URL : `?engagement=<id-engagement>`
  * Valeur par défaut si non spécifié : `"default"` (Socle transverse d'entreprise) ou `"nordwave-mcx-2027"` (Engagement opérationnel de référence).
* **Isolation physique stricte (`ADR-0015`)** :
  Le plan Connaissances (`data/knowledge.kuzu` / `.lbug`) et chaque engagement (`data/engagements/<id>.lbug`) résident dans des fichiers physiques distincts. Aucune jointure Cypher inter-plans n'est autorisée. Le routeur de connexion (`open_connection`) vérifie l'autorisation (`authorise()`) avant d'ouvrir la base de l'engagement.

### 2.2 Politique d'Erreur & Résilience (« Fail Loud »)
Conformément aux conventions de robustesse, le Hub rejette le repli silencieux (*silent fallback*). En cas d'anomalie, le Hub retourne un code HTTP explicite accompagné d'un corps JSON structuré :
```json
{
  "status": "error",
  "error": "Description explicite et actionnable du diagnostic d'erreur"
}
```
* `400 Bad Request` : Paramètre manquant, JSON malformé ou non conforme au schéma.
* `401 Unauthorized` : Jeton absent ou invalide.
* `403 Forbidden` : Jeton valide mais hors des portées de l'engagement demandé (`{"status": "error", "error": "forbidden", "engagement": "<id>"}`). Avant K9, ces cas répondaient `500` sur les routes d'engagement ; seul le code d'état change, les formes de succès sont inchangées.
* `400 Bad Request` (identifiant) : un identifiant d'engagement qui n'est pas `[a-z0-9-]+` est refusé (`{"status": "invalid_argument", "argument": "engagement", ...}`).
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
    "snapshot_id": "snapshot-2026-09-17-fa1ecf2",
    "source_revision": "fa1ecf2b8be24ab7ccdea2cea6e1fd8d140ad485",
    "payload_sha256": "sha256:beb4c7cd2389cf7219871abba69f657e68562240d039e1fcf85ddb15b3068d7d",
    "created_at": "2026-09-17T14:40:46Z"
  }
}
```

---

### 3.2 `GET /snapshot/latest` — Instantané Scellé Canonique (Mode 2)
Retourne l'instantané scellé le plus récent de la base de connaissances et de l'état d'architecture, scellé par empreinte SHA-256. Utilisé par les composants déconnectés (Archinex Offline-First, Document Engine, enclaves souveraines).
* **Accès** : Public / Cacheable (avec support de l'en-tête `ETag`).
* **En-têtes de réponse** :
  * `ETag: sha256:<hash>`
  * `Cache-Control: public, max-age=3600`
* **Réponse HTTP 200** :
```json
{
  "snapshot_id": "snapshot-2026-09-13-e08939b",
  "created_at": "2026-09-13T19:08:15Z",
  "source_revision": "e08939b3471c2aaf6a50245a83cfe926d7235766",
  "payload_sha256": "sha256:1c9b7f067bf4d544fd2c9019b130e2c036bda3bd7ea893eea9923f1d5bc66314",
  "schema_version": "1.0",
  "applicability_index": {
    "ADR-0001": {
      "domains": ["network-automation", "cloud-platform"],
      "phases": ["BUILD"],
      "rules": ["rule:adr-0001"]
    }
  }
}
```

---

### 3.3 `POST /api/rfp/shred-to-candidates` — Dépouillement CCTP & Export Candidats
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

### 3.4 `POST /api/elicitation/trigger` — Déclenchement Asynchrone d'Élicitation
Analyse les lacunes (gaps) d'un engagement et produit des questions ciblées de niveau L2 routées aux rôles d'experts.
* **Usage** : Déclenché out-of-band (à la demande de l'architecte ou via l'orchestrateur de build), sans couplage bloquant dans le sas d'admission.
* **Corps de requête** :
```json
{
  "engagement": "your-engagement"
}
```
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 3,
  "data": {
    "engagement": "your-engagement",
    "total_gaps_targeted": 3,
    "questions_created": 3,
    "questions": [
      {
        "id": "Q-RFP-011",
        "engagement": "your-engagement",
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

### 3.5 `GET /api/elicitation/questions` — Consultation des Questions Ouvertes
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

### 3.6 `GET /api/arbitration/board` — Tableau de Maturité d'Architecture (L0 à L4)
Expose la maturité d'ingénierie par sujet technique pour affichage direct dans les outils consommateurs.
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

### 3.7 `GET /api/arbitration/conflicts` — Controverses et Conflits d'Architecture
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

### 3.8 `GET /api/arbitration/statements` — Énoncés d'Architecture Actifs
Retourne les énoncés d'architecture (`Statement`) associés à un engagement, avec filtrage optionnel par sujet, section ou statut.
* **Paramètres de requête** :
  * `engagement` *(optionnel via query ou header `X-Engagement-Id`)* : Identifiant d'engagement (ex: `nordwave-mcx-2027`).
  * `subject` *(optionnel)* : Nom du sujet technique (ex: `mcx-services`).
  * `section` *(optionnel)* : Section documentaire (ex: `4.2`).
  * `status` *(optionnel)* : `active` | `under_review` | `contested`.
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 2,
  "data": [
    {
      "id": "STMT-001",
      "subject": "mcx-services",
      "predicate": "implements",
      "value": "3GPP TS 23.379 (MCPTT)",
      "confidence": "verified",
      "authority": "client-rfp",
      "status": "active"
    }
  ]
}
```

---

### 3.9 `POST /api/knowledge/suggestions` — Boucle de REX et Curation Amont
Permet de soumettre un motif éprouvé, un arbitrage ou une correction vers la gouvernance du Hub.
* **Corps de requête** :
```json
{
  "title": "Arbitrage HSM SecNumCloud : Partitionnement multi-tenant",
  "rationale": "Le CCTP impose une ségrégation stricte par opérateur.",
  "suggested_change": "Mettre à jour PAT-004 en recommandant des cartes dédiées...",
  "author": "lead-architect@example.com",
  "source_engagement": "your-engagement"
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

### 3.10 `GET /api/compliance/conformity-snapshot` — Snapshot de Conformité Scellé
Produit un instantané réglementaire scellé par checksum SHA-256 calculé sur le profil strict `canonical-json (v1)`.
* **Paramètres de requête** :
  * `framework` : `SecNumCloud` | `ISO27001` | `NIS2` | `3GPP` | `ALL` (défaut : `ALL`).
  * `source_system` *(optionnel)* : `knowledge-hub` (défaut) | `tuleap` (rétrocompatibilité).
* **Réponse HTTP 200** :
```json
{
  "snapshotId": "kh-demo-engagement-2027-secnumcloud-1789311842",
  "sourceSystem": "knowledge-hub",
  "schemaVersion": "2.0",
  "createdAt": "2026-09-17T15:04:02Z",
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
          "programRef": "DEMO-MCX-2027",
          "lotRefs": [],
          "pbsRefs": []
        }
      }
    ]
  }
}
```

---

### 3.11 `GET /api/skills/matrix` — Matrice de Staffing & Risque WBS
Calcule l'adéquation entre les compétences requises par l'architecture du projet et les ressources mobilisées.
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "count": 11,
  "data": {
    "engagement": "your-engagement",
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

### 3.12 `POST /api/documents/zero-draft-blueprint` — Génération Blueprint & ProseStore Initial
Génère le squelette formel de document d'architecture (`DocumentBlueprint`) et son magasin de prose initial (`ProseStore`) à partir des actifs du Hub et de l'engagement ciblé.
* **Corps de requête** :
```json
{
  "engagement": "your-engagement",
  "project_title": "Système d'Architecture Télécom & Plateforme Sécurisée",
  "client_name": "Demo Operator"
}
```
* **Réponse HTTP 200** :
```json
{
  "status": "ok",
  "blueprint": {
    "documentId": "your-engagement-hld-zero-draft",
    "title": "HLD — Système d'Architecture Télécom & Plateforme Sécurisée",
    "sections": []
  },
  "proseStore": {
    "contexte-projet": {
      "blockId": "contexte-projet",
      "text": "Le présent document décrit l'architecture cible..."
    }
  }
}
```

---

### 3.13 `POST /api/prose/suggest-batch` — Assistance de Rédaction Prose par Lot (ADR-DE-02)
Fournit des suggestions de rédaction pour les blocs de prose de `document-engine` en exploitant les motifs d'architecture du Knowledge Hub, sans jamais altérer directement le `ProseStore` du compilateur pur.
* **Corps de requête** :
```json
{
  "requests": [
    {
      "blockId": "contexte-projet",
      "anchorIds": ["ADR-0014", "PAT-001"],
      "instructions": "Souligner les contraintes de haute disponibilité et de souveraineté."
    }
  ]
}
```
* **Réponse HTTP 200** :
```json
{
  "drafts": {
    "contexte-projet": "Conception validée pour le bloc 'contexte-projet' : ..."
  },
  "warnings": [],
  "basedOnModelHash": "fa1ecf2b8be24ab7",
  "generatedAt": "2026-09-17T16:00:00Z"
}
```

---

### 3.14 `GET /api/knowledge/search` - Recherche d'Actifs

Recherche plein texte dans les actifs du plan Connaissances.

- `q` : Texte de recherche libre.
- `type` *(optionnel)* : `decision` | `principle` | `pattern` | `glossary` | `skill`.
- `domain` *(optionnel)* : Filtre par domaine.

```json
{"status": "ok", "count": 3, "data": [{"id": "ADR-0015", "type": "decision", "title": "Separation Physique Dual-Plane"}]}
```

---

### 3.15 `GET /api/knowledge/engagements` - Liste des Engagements

Decouverte dynamique des engagements actifs.

```json
{"status": "ok", "count": 2, "data": [{"id": "nordwave-mcx-2027"}, {"id": "demo-engagement-2027"}]}
```

---

### 3.16 `GET /api/compliance/frameworks` - Liste des Referentiels

Liste les 14 referentiels reglementaires supportes.

```json
{"status": "ok", "count": 14, "data": [{"id": "NIS2"}, {"id": "3GPP"}]}
```

---

### 3.17 `GET /api/compliance/frameworks/applicable` - Referentiels Applicables

Retourne ou met a jour les referentiels applicables a un engagement.

- Methodes : `GET` (lecture) / `PUT` ou `POST` (mise a jour).
- `engagement` *(optionnel)* : Identifiant d'engagement.

```json
{"status": "ok", "engagement": "nordwave-mcx-2027", "applicable_frameworks": ["NIS2", "3GPP", "GSMA"]}
```

---

### 3.18 `GET /api/skills` - Liste du Referentiel de Competences

Liste les 9 competences canoniques d'ingenierie telecom et securite.

- `domain` *(optionnel)* : Filtre par domaine.

```json
{"status": "ok", "count": 9, "data": [{"id": "SKL-CRYPTO-HSM", "domain": "security", "criticality": "critical"}]}
```

---

### 3.19 `GET /snapshot/{snapshot_id}` - Instantane Scelle par Identifiant

Retourne un instantane scelle par son identifiant unique (meme format que section 3.2).

- Parametre URL : `snapshot_id` (ex: `snapshot-2026-09-17-fa1ecf2`).
- HTTP 404 si l'identifiant est inconnu.

---


## 5. Ajouts v1.x

Les versions mineures n'ajoutent que des interfaces ou des champs **optionnels** (voir [`VERSIONING.md`](../VERSIONING.md)). Les interfaces `1.0` restent gelées (`tests/contract/frozen/`). La version courante est exposée par `GET /health` et `get_graph_summary` (`schema_version`) ; le format de l'instantané scellé reste en `schema_version: "1.0"`.

### 5.1 Contrat 1.1 — Paquet de doctrine et juge d'option

Deux interfaces **100 % déterministes** (aucun LLM côté serveur) destinées aux agents consommateurs (Archinex) : *« quelle doctrine s'applique à ce sujet ? »* et *« cette option respecte-t-elle la doctrine ? »*. Seuls les actifs `status: active` sont servis.

#### 5.1.1 `GET /api/knowledge/context` — outil MCP `get_doctrine_context`

| Paramètre | Type | Défaut | Rôle |
|---|---|---|---|
| `subject` | string (requis) | — | Texte libre décrivant le sujet |
| `domains` | list[str] | `[]` | Filtre sur le `domain` des actifs (un domaine parent couvre ses sous-domaines `parent/enfant`) |
| `frameworks` | list[str] | `[]` | Référentiels exigés : **tous** leurs contrôles actifs sont inclus (`required: true`) |
| `phase` | str | `null` | Filtre `phase` (`BID`, `BUILD`, `RUN`) |
| `max_items` | int (1–200) | `20` | Nombre maximum d'éléments |
| `max_chars` | int (200–100000) | `8000` | Budget total des extraits |

En REST, les listes s'écrivent `?frameworks=NIS2&frameworks=SecNumCloud` ou `?frameworks=NIS2,SecNumCloud`.

Classement : correspondance de termes (titre, `terms`, domaine, `applicability`, corps ; normalisation minuscules/accents/pluriels et synonymes du glossaire — entrées « A / B » et [`data/kb/glossary/synonyms.yaml`](../../data/kb/glossary/synonyms.yaml)), seuil de pertinence 0,2 ; ordre **principe > contrôle exigé > pattern > ADR > autre contrôle**, puis pertinence, puis identifiant. `excerpt` = section la plus pertinente, coupée proprement ; la somme des extraits ne dépasse pas `max_chars` ; `truncated: true` si un élément a été omis ou coupé.

```json
{
  "status": "ok",
  "count": 12,
  "data": {
    "items": [
      {
        "typed_id": "principle:P-002", "id": "P-002", "type": "principle", "title": "Human in the loop",
        "status": "active", "confidence": "verified", "domain": ["network-automation", "security"],
        "excerpt": "Detection is automatic, decision is human, execution is automated. …",
        "source_ref": "data/kb/principles/P-002.md", "relevance": 0.43, "has_checks": true,
        "framework": null, "required": false
      }
    ],
    "truncated": false,
    "snapshot_id": "snapshot-2026-09-29-…"
  }
}
```

Schéma : [`schemas/doctrine_context.schema.json`](../../schemas/doctrine_context.schema.json) — types `DoctrineContext*` de [`schemas/types.ts`](../../schemas/types.ts).

#### 5.1.2 `POST /api/knowledge/check` — outil MCP `check_option`

Corps : `{"option": {"title", "description", "statements": [{"subject", "predicate", "value"}]}, "subject", "domains", "frameworks"}` (seul `option.title` est requis).

Le juge évalue les **clauses de contrôle structurées** (`checks`) du front-matter des actifs actifs :

```yaml
checks_status: draft          # draft | validated (seul un relecteur humain valide)
checks:
  - id: P-002-C1
    kind: requires            # requires | forbids
    when: {terms_any: [closed-loop, auto-remediation]}     # et/ou terms_all
    expect: {terms_any: [human-approval, supervised]}      # requires uniquement
    message: "Toute boucle fermée doit rester supervisée par un humain."
```

- `forbids` : si `when` correspond → `violates` ; `requires` : si `when` correspond → `supports` si `expect` correspond, sinon `violates` ; sinon la clause ne s'applique pas.
- Correspondance lexicale sur `title`, `description` et les `statements`, même normalisation que 5.1.1 ; une occurrence précédée d'une négation (`no`, `not`, `without`, `sans`, `pas`…) ne compte pas.
- Un actif pertinent sans clause applicable → `unassessed` (`check_id: null`) : c'est au vérificateur côté client de juger.
- **Tout contrôle actif d'un référentiel de `frameworks` est toujours retourné**, au minimum en `unassessed`.
- Ordre : `violates`, `supports`, `unassessed`, puis priorité de type et identifiant. Champ additionnel `check_status` (`draft` | `validated` | `null`).

```json
{
  "status": "ok",
  "count": 33,
  "data": {
    "verdicts": [
      {"typed_id": "principle:P-002", "check_id": "P-002-C1", "verdict": "violates",
       "message": "Any closed loop must stay supervised: …", "matched_terms": ["closed loop", "auto-remediation"],
       "excerpt": "…", "source_ref": "data/kb/principles/P-002.md", "check_status": "draft"},
      {"typed_id": "control:NIS2-ART21-2A", "check_id": null, "verdict": "unassessed", "message": null,
       "matched_terms": [], "excerpt": "…", "source_ref": "data/kb/controls/NIS2/NIS2-ART21-2A.md", "check_status": null}
    ],
    "summary": {"supports": 0, "violates": 3, "unassessed": 30},
    "method": "deterministic-checks-v1",
    "snapshot_id": "snapshot-2026-09-29-…"
  }
}
```

Schéma : [`schemas/check_result.schema.json`](../../schemas/check_result.schema.json) — types `CheckOptionRequest`, `CheckResult`, `CheckVerdict` de [`schemas/types.ts`](../../schemas/types.ts).

> Les clauses actuellement publiées (P-001, P-002, P-009, P-012, P-015) sont des **brouillons** (`checks_status: draft`) à valider par l'expert via le cycle de revue de la base. Évaluation : `make eval-check` (rappel des violations attendues sur `tests/evals/datasets/check_option_v1.jsonl`, annotations à valider).

Erreurs : `400` + `invalid_argument` (`subject`, `max_items`, `max_chars`, `domains`, `frameworks`, `option`, `option.title`, `option.statements`).

---

### 5.2 Contrat 1.2 — Cycle d'enrichissement de la base (candidats)

Toute connaissance nouvelle passe par une **file persistée**, des **contrôles automatiques déterministes** et une **revue humaine** avant publication. Modèle : [`schemas/kb_candidate.schema.json`](../../schemas/kb_candidate.schema.json) (types `KbCandidate*` de [`schemas/types.ts`](../../schemas/types.ts)).

| Route | Outil MCP | Rôle | Codes |
|---|---|---|---|
| `POST /api/knowledge/candidates` | `submit_kb_candidate` | Créer un candidat ; les contrôles s'exécutent immédiatement | `201`, `400` |
| `GET /api/knowledge/candidates?status=&source=&domain=&engagement=` | `list_kb_candidates` | Lister (plus récents d'abord) | `200` |
| `GET /api/knowledge/candidates/{id}` | `get_kb_candidate` | Détail (contrôles, revues, historique) | `200`, `404` |
| `PATCH /api/knowledge/candidates/{id}` | `review_kb_candidate` | Revue `{action: accept\|amend\|reject, reviewer, reason, amended_content?}` — **scope `kb:review` requis** | `200`, `400`, `403`, `404`, `409` |

Cycle : `proposed` → (`checks_failed` \| `in_review`) → `accepted` \| `rejected` → `published`.

- **Contrôles** (`checks[]`, `pass | fail | warn`) : `schema` (gabarit et front-matter du type), `references` (actifs cités existants), `duplicate` (warn, suggère un `amendment`), `anonymization` (**fail** : liste noire `data/kb/anonymization_denylist.txt`, adresses IPv4/IPv6 et CIDR hors plages de documentation ; warn : volumes identifiants), `doctrine_conflict` (warn : `check_option` sur le contenu ; l'acceptation exige alors `supersedes` ou un motif d'exception), `llm_unreviewed` (warn si `production_mode: llm-derived`), `previously_rejected` (warn). Un seul `fail` → `checks_failed`.
- **Routage** : `assigned_owner` d'après le domaine (`data/kb/owners.yaml`, un sous-domaine hérite de son parent), notification Discord / ntfy / e-mail (SMTP désactivé par défaut). Relance au-delà de 5 jours ouvrés : `kb remind`.
- **Revue** : le relecteur est un propriétaire déclaré ; motif obligatoire pour `amend` et `reject` ; `amend` = acceptation d'un contenu modifié (contrôles rejoués). **Seconde revue** par un **autre** propriétaire si le candidat touche un principe ou contient `supersedes`. Le jeton public de démo ne peut pas relire.
- **Promotion / publication** (CLI hors ligne, mainteneur) : `kb promote <id>` écrit l'actif dans `data/kb/` avec `status: active`, `confidence` **calculée depuis les preuves** (mesure/audit ou ≥ 2 engagements → `verified` ; doc éditeur → `vendor-stated` ; sinon `assumed` ; `llm-derived` non relu → non publiable), `last_reviewed`, `validated_by`, `validated_at` ; `kb publish` réingère, scelle un instantané, écrit `data/kb/CHANGELOG.md`, notifie les consommateurs et passe les candidats en `published`. Le commit git reste manuel.
- Pour un non-relecteur, le contenu d'un candidat bloqué par `anonymization` est masqué.

**Compatibilité** : `suggest_knowledge_improvement` et `POST /api/knowledge/suggestions` gardent la même entrée et la même sortie ; en interne ils créent un candidat `kind: rex`, et `data` gagne le champ **optionnel** `candidate_id`. Champ d'entrée REST optionnel `source_system` (`document-studio` par défaut). La notification historique est conservée.

---

### 5.3 Contrat 1.3 — Couverture réglementaire

- **Outil MCP** `get_framework_coverage(frameworks: list[str])` et **champ optionnel** `coverage` de `GET /api/compliance/frameworks/applicable` (la forme existante `status`, `engagement`, `applicable_frameworks`, `count` est inchangée). Schéma : [`schemas/framework_coverage.schema.json`](../../schemas/framework_coverage.schema.json).

```json
"coverage": {
  "NIS2": {
    "status": "covered | partial | missing",
    "version": "2022/2555",
    "expected": 19,
    "present": 10,
    "validated": 0,
    "missing_ids": ["NIS2-ART20-1", "…"],
    "declared_by": null,
    "provisional": true,
    "manifest": true
  }
}
```

- `covered` exige que toutes les exigences attendues du manifeste `data/kb/controls/<FW>/_manifest.yaml` (généré depuis une source par `kb ingest-framework`) soient présentes, `active`, validées (`validated_by`) **et** que l'expert ait déclaré la couverture (`kb declare-coverage`, refusé sinon). Un référentiel sans contrôle dans la base → `missing` ; un manifeste absent ou provisoire → `expected: null` ou `provisional: true`, jamais `covered`. Rapport : [`docs/COVERAGE.md`](../COVERAGE.md).
- Chaîne hors ligne (mainteneur) : `kb ingest-framework` → `kb suggest-links` (LLM local optionnel, sorties `llm-derived`) → `kb review-sheet` → `kb apply-review` → `kb declare-coverage`. Un contrôle peut déclarer `satisfied_by: [P-…, PAT-…]` (relation `IMPLEMENTS` ingérée dans le graphe) et `covers: [...]` (exigences qu'il couvre).

### 5.4 Contrat 1.4 — Identité de l'expert (client délégué)

Un client de confiance (Archinex) agit **au nom d'un expert** : il envoie son jeton de service, qui porte le scope `kb:delegate` (à côté de `kb:review`), et l'en-tête `X-Actor-Email: <e-mail de l'expert>`.

- L'e-mail n'est pris en compte **que** si le jeton porte `kb:delegate` ; sinon il est ignoré (aucune usurpation par simple en-tête). Il est résolu en handle par le registre des propriétaires (`data/kb/owners.yaml`, ou la base de gouvernance une fois `kb migrate-governance` exécuté). E-mail inconnu → `403`.
- `PATCH /api/knowledge/candidates/{id}` avec un expert délégué : le relecteur **est** l'expert (`reviewer` peut être omis ; s'il est fourni et diffère → `403`). L'expert doit être propriétaire du domaine du candidat (ou d'un domaine parent), `default_owner`, ou porter le rôle `kb:maintain` ; sinon `403`. L'historique enregistre le handle, jamais l'e-mail.
- Sans `X-Actor-Email`, le comportement 1.3 est inchangé.
- **Outil MCP** `get_kb_me()` et `GET /api/knowledge/me` : `{handle, email, kb_roles, owned_domains, pending_reviews}` ; `403` sans acteur ou pour un e-mail inconnu. Schéma : [`schemas/kb_me.schema.json`](../../schemas/kb_me.schema.json). Un propriétaire du registre a implicitement `kb:review` ; `kb:evaluate`, `kb:maintain` et `kb:admin` sont portés par le champ `roles` du registre.
- File des candidats : `CANDIDATES_BACKEND=sql` (SQLite ou PostgreSQL, `GOVERNANCE_DATABASE_URL`), le backend `gcs` jamais implémenté est retiré.
- Limite connue : un jeton de service compromis permet d'usurper n'importe quel expert ; authentification forte et RBAC suivis par l'issue [#7](https://github.com/MauriceIsrael/LLMOps/issues/7).

### 5.5 Contrat 1.5 — Revue et sollicitation des experts

Toutes ces routes exigent le scope `kb:review`. Celles qui agissent pour un expert exigent aussi l'acteur du §5.4 (`kb:delegate` + `X-Actor-Email`). Sans base de gouvernance (`GOVERNANCE_DATABASE_URL`), les fonctions qui en dépendent répondent `503` (enveloppe `status: "unavailable"`) ; la boîte de revue reste calculée depuis la file.

| Route | Outil MCP | Rôle |
|---|---|---|
| `GET /api/knowledge/reviews/inbox` | `get_review_inbox` | Candidats qui attendent l'acteur : `reason` = `review` (assigné), `second_review` (second relecteur requis) ou `advice` (avis demandé) ; du plus ancien au plus récent ; `due_at` = 5 jours ouvrés. |
| `POST /api/knowledge/candidates/{id}/assign` `{handle, reason?}` | `assign_kb_candidate` | Réassigne un candidat `in_review` ; réservé au propriétaire assigné ou à `kb:maintain` (`403`), `handle` inconnu → `400`. |
| `POST /api/knowledge/candidates/{id}/request-review` `{handle, kind, message?, due_at?}` | `request_kb_review` | Crée une demande `second_review` ou `advice` (`201`) ; réservé à un propriétaire du domaine ou `kb:maintain`. Un avis n'est pas une décision. |
| `POST` / `GET /api/knowledge/candidates/{id}/comments` | `comment_kb_candidate` | Fil de discussion (`201`) ; un commentaire n'est pas une décision. |
| `GET /api/knowledge/events?since=<curseur>&limit=` | — | Flux en ajout seul `{events, next_cursor}` ; chaque événement porte `recipients: [handle]`. Types : `candidate.submitted`, `candidate.assigned`, `review.requested`, `candidate.reviewed`, `candidate.commented`, `candidate.promoted`, `candidate.published`, `reminder.due`, `owners.updated` (`eval.updated` et `coverage.changed` arrivent avec les lots suivants). |
| `GET /api/knowledge/owners` | `list_domain_owners` | Registre sans secrets de notification. |
| `PUT /api/knowledge/owners` | — | Remplace le registre ; rôle `kb:admin` de l'expert, ou scope `kb:admin` du jeton quand aucun expert n'agit (amorçage). Validation : rôles connus, e-mails uniques, domaines et `default_owner` cohérents. Les webhooks Discord/ntfy existants sont conservés. Journalisé (`owners.updated`). |

- La seconde revue d'un principe (ou d'un `supersedes`) crée automatiquement la demande `second_review` vers le second propriétaire ; la revue de cet expert la clôt.
- `kb remind` émet `reminder.due`. Un propriétaire marqué `delegated` (compte Archinex) n'est plus notifié sur Discord, ntfy ou e-mail : Archinex délivre la notification depuis le flux.
- Schémas : [`review_inbox`](../../schemas/review_inbox.schema.json), [`governance_event`](../../schemas/governance_event.schema.json).

### 5.6 Contrat 1.6 — Atelier de doctrine et évaluations

REST uniquement. `kb:review` est exigé partout sauf pour les gabarits, le contrôle à blanc, la simulation et le dépôt de retours (comme la soumission). Les routes d'évaluation et de retours exigent la base de gouvernance (`503` sinon) ; la simulation retombe sur le JSONL de `check_option_v1`. Les actions d'évaluateur exigent un expert agissant (§5.4) avec le rôle `kb:evaluate` (ou `kb:maintain`) ; l'annotateur enregistré est cet expert.

| Route | Rôle |
|---|---|
| `GET /api/knowledge/templates/{asset_type}` | Gabarit : champs de front matter avec vocabulaires (domaines, phases, confiance), sections attendues, prochain identifiant libre, squelette Markdown. Types : `principle`, `pattern`, `decision`, `control`, `glossary`. |
| `POST /api/knowledge/candidates/validate` | Contrôles à blanc d'une soumission (mêmes 7 contrôles) : `would_be_status`, propriétaire qui serait assigné, seconde revue requise. Ne crée rien, ne notifie personne. |
| `POST /api/knowledge/checks/simulate` `{asset_id, checks, dataset?, only_validated?, options?, frameworks?}` | Remplace les clauses de l'actif dans un index temporaire et compare avant/après sur les cas d'évaluation et sur des options libres : régressions, améliorations, rappel et précision. Déterministe, sans écriture. |
| `GET /api/knowledge/evals/{dataset}` | Cas (avec `annotation_status`, annotateur, date) et dernières exécutions. |
| `POST …/cases`, `PATCH …/cases/{id}` | Ajouter un cas `proposed` ; annoter (`expected`, `annotation_status` ∈ `proposed|validated|rejected`, un cas validé exige des verdicts attendus). |
| `POST …/runs` `{validated_only?}`, `GET …/runs/{id}` | Exécute l'évaluation (celle de `make eval-check`), historise rappel, précision et cas manqués, émet `eval.updated`. |
| `POST /api/knowledge/verdict-feedback` | Retour d'un humain sur un verdict (`wrong_violation` \| `missed_violation` \| `correct`, justification, option). Rapporteur = expert agissant, sinon jeton. |
| `GET /api/knowledge/verdict-feedback?status=` | Retours à traiter. |
| `POST …/verdict-feedback/{id}/convert` | Par un évaluateur : `{to: eval_case, dataset, expected}` (nouveau cas `proposed`), `{to: amendment, asset_type, target_asset_id, proposed_content}` (candidat d'amendement) ou `{to: dismiss}` ; un retour déjà traité → `409`. |

- `kb migrate-governance` importe `tests/evals/datasets/check_option_v1.jsonl` (idempotent) ; `make eval-check` lit la base quand elle est configurée.
- Schémas : [`asset_template`](../../schemas/asset_template.schema.json), [`clause_simulation`](../../schemas/clause_simulation.schema.json), [`eval_dataset`](../../schemas/eval_dataset.schema.json).

### 5.7 Contrat 1.7 — Ingestion des référentiels par l'API

REST uniquement, sur la base de gouvernance (`503` sinon). C'est la chaîne hors ligne de la §5.3 rejouée ligne à ligne, sans CSV : le texte est extrait dans un sous-processus borné (20 Mo, 120 s), les brouillons et les décisions vivent en base, `apply` exécute le même `apply_review` que `kb apply-review`. Aucune route n'appelle un LLM.

| Route | Rôle |
|---|---|
| `POST /api/frameworks/ingestions` (multipart : `file`, `framework`, `version`, `tag?`) | `kb:maintain`. Sources `.pdf .html .txt .md .docx` ; le référentiel doit avoir un splitter (`pipelines/frameworks/splitters/`), sinon `400` avec la liste disponible. Écrit le manifeste dans la KB, réinitialise la déclaration de couverture si la version ou la source change, émet `coverage.changed`. `201`. |
| `GET /api/frameworks/ingestions`, `GET …/{id}` | Ingestions et référentiels disposant d'un splitter ; exigences avec texte légal, liens et critères proposés, décision et statut de chaque ligne (`pending`, `decided`, `applied`, `failed`). |
| `PATCH …/{id}/rows/{requirement_id}` `{decision: accept\|amend\|reject\|"", links?, acceptance_criteria?, comment?}` | Le relecteur est l'expert agissant, propriétaire du domaine de l'exigence (ou `kb:maintain`). Liens inconnus → `400` ; `amend` exige liens ou critères. |
| `POST …/{id}/link-proposals` `{model?, proposals: [{requirement_id, satisfied_by, acceptance_criteria}]}` | `kb:maintain`. Propositions du LLM local du client, enregistrées `llm-derived` ; identifiants inconnus écartés et comptés. Elles ne décident rien. |
| `POST …/{id}/apply` | `kb:maintain`. Crée les candidats `framework_ingestion` revus et promeut les acceptés (écriture dans `data/kb/controls/<FW>/`). Statut `applied` ou `partially_applied`. |
| `POST /api/frameworks/{fw}/coverage-declaration` | Déclaration par l'expert agissant ; `409` avec la liste de ce qui manque tant que tout n'est pas actif et validé ; émet `coverage.changed`. |

- Schéma : [`framework_ingestion`](../../schemas/framework_ingestion.schema.json). Dépendance ajoutée : `python-multipart`.
- Limite : la promotion écrit directement dans `data/kb/` du serveur (stockage persistant en exploitation normale ; perdue au redémarrage en mode démo, cf. D2).

### 5.8 Contrat 1.8 — Promotion, publication et santé de la base

REST uniquement. Actions réservées à un expert agissant avec `kb:maintain` (§5.4).

| Route | Rôle |
|---|---|
| `POST /api/knowledge/candidates/{id}/promote` | Équivalent de `kb promote` : écrit l'actif accepté dans `data/kb/` du serveur (`status: active`, confiance calculée, `validated_by` = relecteurs). `409` si le candidat n'est pas accepté ou déjà promoté. |
| `POST /api/knowledge/publications` | Équivalent de `kb publish` : reconstruit le graphe (dans un fichier voisin échangé atomiquement), scelle un instantané, écrit le `CHANGELOG`, notifie les consommateurs, passe les candidats promus en `published` avec l'identifiant d'instantané. Rien à publier → `200`, `published: []`. |
| `GET /api/knowledge/health` | Indicateurs (scope `kb:review`) : actifs par type et domaine, actifs sans `validated_by`, clauses (dont brouillons) et part de verdicts `unassessed` de la dernière exécution d'évaluation, couverture par référentiel, file par propriétaire (attente la plus longue) et candidats en retard (≥ 5 jours ouvrés), dernière évaluation, dernier instantané, `storage: {persistent, mode}`. |

- **Mode démo** : avec `LLMOPS_STORAGE_PERSISTENT=false` (déploiement Cloud Run sans volume), `promote` et `publications` répondent avec `warnings: ["ephemeral-storage"]` — la doctrine écrite est perdue au prochain redémarrage — et `health.storage.mode` vaut `demo`. L'état de gouvernance (candidats, revues, évaluations) reste en base. Décision D2 : aucun contournement.
- La publication écrit sur le disque du serveur ; le commit git de `data/kb/` reste l'acte du mainteneur en exploitation normale. Schéma : [`kb_health`](../../schemas/kb_health.schema.json).

### 5.9 Contrat 1.9 — Similarité sémantique (vecteurs calculés par le client)

Plan : [`PLAN-IMPLEMENTATION-Similarite-Reutilisation.md`](../plans/PLAN-IMPLEMENTATION-Similarite-Reutilisation.md). REST uniquement, base de gouvernance requise (`503` sinon), scope `kb:review`. **LLMOps ne contient aucun modèle** : le client (Archinex) calcule les vecteurs ; LLMOps les stocke avec le nom et la version du modèle et calcule un cosinus, de façon déterministe.

| Route | Rôle |
|---|---|
| `GET /api/knowledge/embeddings/pending?model=` | Actifs et contrôles **actifs** dont le vecteur manque (`missing`) ou est périmé (`stale`), avec le **texte à encoder** (titre, puis sections qui énoncent l'actif ; titre français des contrôles) et son SHA-256. `models` liste les modèles déjà stockés. |
| `PUT /api/knowledge/embeddings` `{model, model_version, items:[{ref, text_sha256, vector, language?}]}` | Dépôt par lot (≤ 500). **Refus (`400`)** si le SHA-256 ne correspond plus au texte courant (vecteur périmé), si l'actif n'est pas actif, si la dimension diffère de celle du modèle, si le vecteur est nul ou non fini, ou si `model_version` diffère de celle déjà stockée (deux versions ne sont jamais mélangées). Avec un expert agissant : rôle `kb:maintain` ; sans expert (synchronisation système) : le jeton de service suffit. |
| `POST /api/knowledge/similar` `{model, vector, query_text?, types?, domains?, top_k?}` | Classement **hybride** : le cosinus est la preuve principale ; la pertinence lexicale du moteur de doctrine (synonymes FR/EN, seulement avec `query_text`) et le domaine ne peuvent que **relever** le score, jamais l'abaisser (d'une langue à l'autre, la preuve lexicale est absente par nature : un vrai rapprochement ne doit pas en être pénalisé). Intensités et seuils dans `data/kb/taxonomy/similarity.yaml` (`status: uncalibrated` tant qu'aucune évaluation ne les a fixés). |

**Un résultat n'est jamais une décision.** Chaque élément porte `requires_confirmation: true` quel que soit le score (décision D8 : tolérance zéro), sa `zone` (`strong`, `possible`, `weak`, ou `superseded` pour un actif remplacé, jamais présenté comme valide), `stale`, sa provenance (`status`, `last_reviewed`, `review_by`, `validated_by`, `validated_at`, `superseded_by`) et ses **hypothèses de validité** (`assumptions`, `assumptions_documented`). `GET /api/knowledge/health` ajoute `embeddings` : par modèle, vecteurs, manquants et périmés. Schéma : [`similar_knowledge`](../../schemas/similar_knowledge.schema.json).

### 5.10 Contrat 1.10 — Réutilisation de la connaissance validée

Plan : [`PLAN-IMPLEMENTATION-Similarite-Reutilisation.md`](../plans/PLAN-IMPLEMENTATION-Similarite-Reutilisation.md) §3.3 et §3.4. **Une réutilisation n'est jamais automatique** (décision D8) : une recherche de similarité (§5.9) ne produit qu'une proposition ; la réutilisation est acquise quand une **personne** a confirmé, une par une, les hypothèses sous lesquelles la décision d'origine est valable.

- **Hypothèses** : champ optionnel `assumptions: [..]` (une hypothèse vérifiable par ligne) et `review_by` (date de réexamen) dans le front matter des décisions, principes et patterns ; schéma `data/kb/schema/frontmatter.schema.json`, gabarit et aide à jour. Une décision soumise **sans** `assumptions` reçoit un avertissement du contrôle `schema`. `GET /api/knowledge/health` liste `assets.decisions_without_assumptions`.
- `POST /api/knowledge/reuse-confirmations` (`201`) : `{subject_fingerprint (SHA-256 du sujet normalisé), subject_label (court, anonymisé), matched_ref, model?, scores?, outcome, assumptions:[{text, status: holds|does_not_hold|unknown, note?}], comment?}`. **Exige une personne agissante** (§5.4, jeton `kb:delegate` + `X-Actor-Email`) ; l'auteur est enregistré (handle s'il est dans le registre, sinon `email:<adresse>`). Journal **en ajout seul**. Aucun texte d'engagement n'est conservé : une empreinte et un libellé anonymisé (les adresses IP, e-mails et noms de la liste d'anonymisation sont refusés).
- **Règles appliquées par le serveur** (`400` / `409`) :
  - `reused` exige que **toutes** les hypothèses documentées de l'actif soient jugées **exactement** (mêmes énoncés qu'à cet instant) et `holds` ;
  - un actif **sans hypothèse documentée** ne peut être ni `reused`, ni `reused_with_exception`, ni `rejected_assumption_fails` (les documenter d'abord par un amendement) ;
  - `reused_with_exception` exige au moins une hypothèse non tenue ou inconnue **et** un commentaire motivé ; `rejected_assumption_fails` exige au moins une hypothèse `does_not_hold` ; `rejected_not_same` exige un commentaire (la raison est mémorisée) ;
  - un actif non `active` ou remplacé ne peut pas être réutilisé (il peut être rejeté) ;
  - `deferred` ne demande rien.
- `GET /api/knowledge/reuse-confirmations?matched_ref=&outcome=&subject_fingerprint=` (`kb:review`) : historique, base de calibration et piste d'audit.
- **Mémoire dans la recherche** : `POST /api/knowledge/similar` accepte `subject_fingerprint` et ajoute à chaque résultat `judgements` (jugements antérieurs de ce sujet, le plus récent d'abord), `previous_confirmation_outdated` (**vrai** si les hypothèses de l'actif ont changé depuis une confirmation : elle ne tient plus, il faut juger la nouvelle liste) et `reuse_summary` (issues par actif, tous sujets confondus). Rien n'est masqué : un rejet passé est **affiché** avec sa raison.
- Schéma : [`reuse_confirmation`](../../schemas/reuse_confirmation.schema.json).

### 5.11 Contrat 1.11 — Évaluation de la similarité (jeu FR/EN)

Plan : §3.5. **Aucun seuil de `similarity.yaml` n'est justifié tant qu'une exécution documentée ne l'a pas fixé.** Base de gouvernance requise (`503` sinon).

- Jeu `similarity_v1` (`tests/evals/datasets/similarity_v1.jsonl`, importé par `kb migrate-governance` et au démarrage) : 16 cas FR/EN en **quatre familles** — `cross_lingual` (même sujet d'une langue à l'autre), `same_words_different_subject` (mêmes mots, autre sujet), `same_topic_different_assumptions` (même thème, hypothèses incompatibles), `out_of_base` (sujet absent). Relations attendues par actif : `same_subject`, `related_not_same`, `same_topic_different_assumptions`, `unrelated`. Les annotations initiales sont **proposées par un agent** (`annotated_by: coding-agent`, statut `proposed`) : seule la validation par un expert les rend probantes.
- `GET /api/knowledge/similarity-evals/{dataset}` (`kb:review`) : cas avec `query_text` (le texte à encoder), langue, famille, relations attendues, statut d'annotation ; dernières exécutions.
- `PATCH …/cases/{case_id}` `{expected?: [{ref, relation}], annotation_status?}` : expert agissant avec `kb:evaluate` ; références inconnues et relations invalides refusées ; un corps sans `expected` ni `annotation_status` → `400`.
- `POST …/runs` `{model, vectors: {case_id: vector}, validated_only?}` (`201`) : **le client fournit les vecteurs des cas** (il détient le modèle) ; LLMOps calcule, de façon déterministe : `recall_at_3`, **`false_strong`** (propositions « strong » erronées, la mesure qui compte), `missed_strong`, `reuse_trap_strong` (cas « même thème, hypothèses différentes » en zone strong : signalés à part, car seules les hypothèses les départagent), le détail par famille et par langue, et un **balayage de seuils** avec `recommended_strong_threshold` (le plus bas seuil sans aucune proposition « strong » erronée, `null` si aucun n'y suffit). Vecteurs manquants, de mauvaise dimension ou modèle inconnu → `400`.
- `GET …/runs/{id}` : exécution et détail par cas. Événement `eval.updated`.
- Fixer un seuil est un acte humain : modifier `data/kb/taxonomy/similarity.yaml` en citant l'exécution, et seulement sur des annotations `validated`.
- Correctif de conception intégré à ce lot (contrat 1.9) : les preuves lexicale et de domaine **relèvent** le score du cosinus sans jamais l'abaisser (d'une langue à l'autre la preuve lexicale est absente ; la pondération initiale pénalisait justement les rapprochements FR ↔ EN). `similarity.yaml` porte désormais `boosts` au lieu de `weights`.
- Schéma : [`similarity_eval_run`](../../schemas/similarity_eval_run.schema.json).

### 5.12 Contrat 1.12 — Métadonnées bilingues à l'ingestion

Complète l'ingestion par l'API (§5.7) pour qu'un contrôle ingéré soit trouvable en français comme en anglais (plan de similarité §3.6). Champs **optionnels** ; la forme existante est inchangée.

- `POST /api/frameworks/ingestions/{id}/link-proposals` : chaque proposition accepte aussi `terms` (termes de recherche FR et EN, au plus 20 de 60 caractères, dédoublonnés et mis en minuscules) et `title_fr` (≤ 200 caractères). Ils sont enregistrés comme **proposés par le modèle du client** (`llm-derived`) et ne décident rien.
- `PATCH …/rows/{requirement_id}` : `terms` et `title_fr` de l'expert (avec `amend`) **remplacent** la proposition. Un `amend` exige au moins un lien, un critère, des termes ou un titre français.
- À l'application : les termes sont **fusionnés** à ceux d'un contrôle existant (jamais remplacés) ; `title_fr` n'est écrit que s'il est absent, **sauf** s'il vient de l'expert (un titre curé n'est jamais écrasé par une proposition de modèle). Le contrôle porte `terms_production_mode` : `llm-proposed-human-approved` ou `human-authored`.
- Un contrôle issu d'une source (`source_sha256`) garde l'appariement par texte légal du découpeur de RFP même une fois qu'il porte des `terms` ; un contrôle curé jamais ingéré n'est apparié que sur ses termes.
- La réponse `GET …/ingestions/{id}` ajoute par exigence `proposed_terms`, `proposed_title_fr`, `terms`, `title_fr`.

### 5.13 Contrat 1.13 — Dépréciation de la partie engagement

Les consommateurs qui gèrent les engagements (Archinex, lots A1 à A4) n'ont plus besoin de ces interfaces ; elles restent servies **à l'identique** (mêmes entrées, mêmes formes, mêmes codes) pendant au moins deux versions mineures, selon [`docs/DEPRECATION.md`](../DEPRECATION.md).

- **Routes dépréciées** : `POST /api/elicitation/trigger`, `GET /api/elicitation/questions`, `GET /api/arbitration/board`, `GET /api/arbitration/conflicts`, `GET /api/arbitration/statements`. Chaque réponse porte l'en-tête `Deprecation: true` et `Link: <…/migration-archinex.md>; rel="deprecation"`.
- **Outils MCP dépréciés** (plan d'engagement) : `get_subject`, `get_subject_trajectory`, `get_board`, `get_statements`, `get_conflicts`, `get_open_questions`, `get_diagram_graph`, `get_render_payload`, `get_dangling_references`, `get_engagement_export`.
- **Champ d'enveloppe** `deprecation: {since, replaced_by, doc}` (optionnel, ajouté aux réponses ci-dessus) ; une ligne `WARNING` est écrite sur le journal `mcp_server.deprecation` (interface, appelant) à chaque appel.
- **Legacy (non déprécié, sans évolution)** : `/api/rfp/shred-to-candidates`, `/api/documents/zero-draft-blueprint`, `shred_rfp`, `generate_zero_draft_hld`, `trigger_rfp_elicitation`, le catalogue de compétences. Aucun signal de dépréciation.
- **Assistance à la rédaction (`POST /api/prose/suggest-batch`, non legacy)** : consommée par le `Document Engine` (ADR-DE-02, fournisseur « Knowledge Hub »). Forme **inchangée** (`drafts`, `warnings`, `basedOnModelHash`, `generatedAt`), contenu **corrigé** : le Hub fournit de la **connaissance, pas un récit**. Chaque brouillon liste la doctrine applicable (`[id] titre (type, confiance) : extrait`) avec la confiance telle que publiée (`vendor-stated` et `assumed` jamais présentées comme vérifiées) et la mention qu'elle ne démontre pas la conformité du projet ; la requête est formée des libellés des éléments ancrés (`context.anchoredItems[].attributes.label`) et de la consigne. **Quand rien ne s'applique, ou quand il n'y a ni libellé ni consigne, aucun brouillon n'est produit** : un avertissement `{blockId, message}` le dit. Avant cette correction la route cherchait dans la base des identifiants du graphe d'engagement (absents) et, à défaut, écrivait une phrase affirmant une « conception validée » ou une conformité « aux motifs d'architecture du Knowledge Hub » que rien n'établissait.
- **Détection de conflits** : `CONFLICT_DETECTION_MODE=legacy|strict` (défaut `legacy`, comportement inchangé). `strict` ne signale que des valeurs **différentes** pour un même prédicat ; `legacy` signale aussi deux auteurs qui écrivent la même valeur. Ne pas changer le défaut sans l'accord écrit de l'équipe Archinex.

### 5.14 Contrat 1.14 — Annulation de la dépréciation de la partie engagement

Le Hub contient deux bases, connaissance et engagement ([ADR-KH-01](../adr/ADR-KH-01-contrats-exposes.md) A10, projet). La dépréciation du §5.13 est **annulée** : les routes `POST /api/elicitation/trigger`, `GET /api/elicitation/questions`, `GET /api/arbitration/{board,conflicts,statements}` et les outils MCP d'engagement sont en service, **sans** en-tête `Deprecation`, **sans** champ d'enveloppe `deprecation`, sans ligne de journal de dépréciation. Entrées, formes et codes sont ceux de la 1.13. Le champ `deprecation` reste un champ optionnel réservé (aucune interface n'est dépréciée en 1.14). Le générateur de document (legacy, lot K4) n'est pas concerné.

### 5.15 Contrat 1.15 — Instantané aligné sur la suite (K1 à K3)

**K1 — sceaux au profil canonical-json v1.** `payload_sha256` de l'instantané scellé (`GET /snapshot/latest`, `fixtures/sealed_snapshot.json`, `data/snapshots/*.json`) et `checksum` de l'instantané de conformité sont calculés par `pipelines/canonical.py` (profil de la suite, 48 vecteurs partagés), plus par `json.dumps`. **Les formes ne changent pas ; la valeur de `payload_sha256` change pour un même contenu** : un consommateur qui recalculait l'ancienne empreinte (JSON indenté, clés triées) doit adopter le profil (nombres au format ECMAScript, clés triées par unité de code UTF-16, `NaN`/`Infinity`/entiers au-delà de 2^53−1 refusés). Un test de garde interdit de calculer un sceau à partir d'un `json.dumps` hors du module. K2 et K3 complètent cette section.

**K2 — enveloppe de canal.** Champs **additifs** de l'instantané scellé (`GET /snapshot/latest`, fixtures, `data/snapshots/*.json`), ceux que le registre de canaux de la suite demande à un émetteur ([`schemas/sealed_snapshot.schema.json`](../../schemas/sealed_snapshot.schema.json)) :

| Champ | Valeur |
|---|---|
| `emitter` | `knowledge-hub` |
| `checksum` | même valeur que `payload_sha256` (`sha256:<hex>` du contenu au profil canonical-json v1) |
| `rebuiltByEmitterTest` | `true` : le test de fraîcheur **reconstruit** le fichier depuis `data/kb` (`tests/contract/test_sealed_snapshot_freshness.py`) et échoue s'il diffère |
| `regenerate` | `poetry run python scripts/export_fixtures.py` |
| `is_provisional`, `provisional_reasons {unripe_subjects, open_conflicts}` | **dérivés** des compteurs : provisoire dès qu'un sujet est sous `L3_decided` ou qu'un conflit est ouvert. Le plan Connaissance ne contient ni sujet ni conflit : ils valent `false`, `0`, `0`. L'instantané d'engagement (lot K11) porte les vrais compteurs |

Les champs en snake_case existants sont conservés. L'enveloppe de la suite place le contenu sous `data` (`snapshotId`, `schemaVersion`…) : cet instantané garde son contenu à plat, pour ne pas le dupliquer ; l'adaptation est un choix à valider avec la suite (voir `docs/SUITE-MAP.md`). **K3 — référence citable.** Une référence de la suite est `KnowledgeRef {sourceId: "knowledge-hub", knowledgeKey, version}` : « une référence partielle n'existe pas ». `knowledgeKey` est la clé typée (`decision:ADR-0001`, `principle:P-002`, `pattern:PAT-006`…) ; `version` est la **révision** de l'élément (champ d'en-tête `revision`, entier ≥ 1, **1 si absent**, relevé par chaque amendement accepté via `kb promote`). Le champ `version` historique n'est pas utilisé : pour un contrôle c'est la révision du texte réglementaire (`2022/2555`, `Rel-18`).

- **Instantané scellé** : chaque actif porte `revision`, `knowledge_ref`, `content` (texte exact, en-tête compris) et `content_sha256`. `provenance.version` n'est plus la constante `"1.0"` mais la révision. `source_path` n'y figure pas.
- **Registre des révisions** `data/kb/version-ledger.json` (ajout seul) : hash du contenu de chaque révision publiée. L'export **refuse** un contenu modifié sans nouvelle révision, et une révision non enregistrée tant que `scripts/export_fixtures.py` (ou `kb publish`) ne l'a pas enregistrée. Les clés retirées restent au registre : un identifiant n'est jamais recyclé. Garantie : le même `{knowledgeKey, version}` résout toujours les mêmes octets.
- **Résolution** : `GET /api/knowledge/assets/{id}[?version=&snapshot=]` (`id` : clé typée ou identifiant nu) et l'outil MCP `get_asset(id, version?, snapshot?)` quand `version` ou `snapshot` est donné. Le contenu vient **de l'instantané désigné** (`latest` par défaut), dont l'empreinte est **vérifiée** avant lecture, ainsi que le hash du contenu. Refus explicites, jamais le contenu courant : `404 version_not_in_snapshot` (avec `available_version`), `404 unknown_key`, `404 snapshot_unavailable`, `400` pour un identifiant d'instantané invalide, `500 snapshot_corrupt` / `content_corrupt`.
- **Hérité, non citable** : `get_asset(id)` sans `version` ni `snapshot` lit toujours la **base vivante** (forme gelée de la 1.x ; `resolved_from: "live-base"` le dit) ; son champ `source_path` reste dans cette forme gelée jusqu'à la 2.0. Les anciennes références `KH:<id>@v1.0.0` (`external_ref`, suggestions) ne sont pas des `KnowledgeRef` et ne sont pas citables.
- **Pas encore couverts** : termes de glossaire et contrôles (leur révision n'est pas portée par cet ajout).

Corrigé au passage : la `version` d'un référentiel (`frameworks[].version`) dépendait de l'ordre des lignes renvoyées par le graphe (GSMA mêle plusieurs versions) ; elle vient désormais du premier contrôle par identifiant.

### 5.16 Contrat 1.16 — Engagements gérés : rôles, membres, audit (K14)

[ADR-KH-01](../adr/ADR-KH-01-contrats-exposes.md) A11. Un engagement qui a une ligne dans le registre (`POST /api/engagements`) est **géré** : il est fermé à tous sauf à ses membres, **dans tous les environnements** (le mode ouvert hors production ne concerne que les engagements non gérés, hérités). Il faut une base de gouvernance (`GOVERNANCE_DATABASE_URL` ou `CANDIDATES_BACKEND=sql`) ; sans elle les routes de gestion répondent `503 governance_database_required` et aucun engagement n'est géré.

**Qui agit.** Une personne agit par un client de confiance : un jeton portant `eng:delegate` qui envoie `X-Actor-Email` (l'en-tête n'a aucun effet pour un autre jeton). Jetons : `eng:service` (lecture sans personne, ex. l'adaptateur de la suite), `eng:create` (créer un engagement). Le jeton d'exploitation (`server_admin`) gère les membres mais **ne lit pas** le contenu.

| Rôle | Actions |
|---|---|
| `reader` | `read` |
| `contributor` | + `contribute` (proposer énoncés et réponses ; rien ne devient affirmé) |
| `decider` | + `decide` (affirmer, arbitrer) |
| `admin` | + `export` (instantané vers la suite), `import` (reprise depuis un autre système), `members` |

| Route | Action requise |
|---|---|
| `POST /api/engagements` `{engagement, confidentiality, admin_email, admin_handle}` | jeton `server_admin` ou `eng:create` ; `201`, `409` si l'engagement existe, `400` sinon |
| `GET`, `PUT /api/engagements/{id}/members` (`{members:[{email, handle, role}]}`) | `members` ; au moins un `admin`, e-mails et handles uniques |
| `GET /api/engagements/{id}/me` | `read` ; `{managed, handle, role, actions, confidentiality}` |
| `GET /api/engagements/{id}/audit?limit=` | `members` ; refus et actions autres que la lecture |

Niveaux de confidentialité : `public`, `internal`, `confidential`. Les e-mails ne sortent jamais du registre dans une réponse d'engagement ni dans l'audit ; l'audit nomme les personnes par handle et les jetons par une empreinte. Refus par rôle : `403 {"error": "forbidden", "action", "reason"}` avec `reason` parmi `actor_required`, `not_a_member`, `role_insufficient` ; un jeton hors portée reste un `403` sans `reason` (K9). Les routes existantes d'engagement demandent `read` ; `trigger`/`shred` avec persistance `contribute` ; `PUT …/frameworks/applicable` `decide`.

### 5.17 Contrat 1.17 — Écriture dans un engagement géré (K15)

Archinex est l'outil de délibération ; le Hub enregistre. Toutes les routes sont sous `/api/engagements/{id}/`, exigent un engagement **géré** (`409 engagement_not_managed` sinon) et les rôles du §5.16. Réponse : `{"status": "ok", "data": …}`.

| Route | Rôle | Effet |
|---|---|---|
| `POST subjects` `{name, definition?}` | `contributor` | crée (`201`) ou retrouve (`200`) un sujet |
| `POST subjects/{name}/maturity` `{level}` | `decider` | avance la maturité ; `L3_decided` et `L4_specified` exigent un énoncé **affirmé** sur le sujet et **aucun conflit ouvert** (`409 no_asserted_statement`, `open_conflict`) |
| `POST statements` `{subject, value, confidence, section?, predicate?, role?, verbatim?, based_on?, origin?}` | `contributor` | propose un énoncé, `status: proposed` |
| `POST statements/{id}/assert` | `decider` | l'énoncé devient `active`, avec `validated_by` et `validated_at` ; ouvre les conflits détectés (`conflicts_opened`) |
| `POST statements/{id}/withdraw` | `contributor` (auteur) ou `decider` | `withdrawn` ; un autre contributeur : `403 not_author` |
| `POST questions` `{question, subject?, section?, …}` | `contributor` | question ouverte |
| `POST questions/{id}/answers` `{value, confidence, …}` | `contributor` | énoncé **proposé** lié à la question, qui devient `answered` |
| `POST requirements` `{requirements: [{id, text, section?, category?, criticality?}]}` | `contributor` | 1 à 500 exigences ; un `id` existant avec le même texte est ignoré (`unchanged`), avec un autre texte : `409 requirement_changed` |
| `POST conflicts/{id}/arbitrate` `{keep_statement_id, reason}` | `decider` | arbitre ; refusé si l'arbitre a écrit un des énoncés en cause |

Règles communes :
- **L'auteur est le membre** (son handle), jamais un nom du corps de requête (`author`, `status`, `validated_by` envoyés sont ignorés).
- **Rien ne naît affirmé.** Personne n'affirme ce qu'il a écrit (`409 self_validation`). Un contenu `origin: "llm-derived"` est proposé comme le reste.
- `confidence` ∈ `verified, designed, vendor-stated, stated-by-client, assumed` ; `verified` exige des preuves (`based_on`). Une valeur inconnue : `400` avec le champ.
- **Idempotence** : l'en-tête `Idempotency-Key` (ou `idempotency_key`) donne le même identifiant ; un élément existant est renvoyé tel quel (`200`, `created: false`), jamais réécrit (une affirmation n'est pas remise à zéro par un rejeu). Les exigences sont idempotentes par leur `id`.
- Colonnes ajoutées à l'énoncé : `origin`, `validated_by`, `validated_at` (additif).

### 5.18 Contrat 1.18 — Instantané scellé d'un engagement (K11)

Le Hub est l'**émetteur** du canal « engagement » vers la suite ([ADR-KH-01](../adr/ADR-KH-01-contrats-exposes.md) A10) ; Archinex, outil de délibération, n'y apparaît pas. Schéma : [`schemas/engagement_snapshot.schema.json`](../../schemas/engagement_snapshot.schema.json), exemple reconstruit par le test de l'émetteur : [`schemas/examples/engagement_snapshot.example.json`](../../schemas/examples/engagement_snapshot.example.json).

| Route | Rôle | Effet |
|---|---|---|
| `POST /api/engagements/{id}/exports` | `admin` | émet l'instantané : `201` `{snapshotRef, created: true, is_provisional}` ; le même état donne le même instantané : `200`, `created: false` |
| `GET /api/engagements/{id}/exports` | `read` | historique des références |
| `GET /api/engagements/{id}/exports/{snapshotId}` | `read` (jeton `eng:service` compris) | l'enveloppe, vérifiée avant d'être servie (`500 snapshot_corrupt` sinon) ; l'instantané d'un autre engagement : `404` |

**Enveloppe** (suite `ExternalSnapshotEnvelope`) : `schemaVersion`, `snapshotId`, `sourceSystem` et `emitter` (`knowledge-hub`), `createdAt`, `sourceRevision`, `checksum`, `data`. `checksum` = sha256 de `data` **seul** au profil canonical-json v1 ; `snapshotId` = `eng-<engagement>-<12 premiers hex du checksum>` : l'identifiant dérive du contenu, un identifiant émis ne désigne jamais un autre contenu. `snapshotRef` = `{sourceSystem, snapshotId, checksum, producedAt}` voyage à part de ce qu'il désigne.

**`data`** : `engagement {id, confidentiality}` (obligatoire), `pins` (version du contrat, instantané de la base de connaissance cité), `is_provisional` et `provisional_reasons {unripe_subjects, open_conflicts}` (**dérivés** : sujet sous `L3_decided` ou conflit ouvert), `requirements`, `subjects` (maturité), `statements` (confiance, `status`, `assertion_level` dérivé, `origin`, `author`, `validated_by`, `validated_at`, `based_on`), `conflicts`, `gaps` (G1 et G2 ; G3 n'est pas calculé), `kb_references` (`KnowledgeRef` résolus depuis l'instantané épinglé) et `unresolved_references`. Personnes : **handles seulement**.

**Refus** (rien n'est produit ni stocké) : `422 verification_failed` avec `problems [{code, path, message}]` (jamais la valeur fautive) pour `EMAIL`, `ASSERTED_WITHOUT_PERSON`, `SELF_VALIDATION`, `AUTHOR_NOT_A_HANDLE`, `VALIDATOR_ON_PROPOSED`, `ARBITRATED_WITHOUT_PERSON`, `DANGLING`, `DUPLICATE_ID`, `PROVISIONAL`, `SEAL`, `SNAPSHOT_ID`, `SCHEMA` ; `422 kb_snapshot_unavailable` si des énoncés citent la base alors que son instantané est inutilisable ; `409 engagement_not_managed`.

**Ce que l'instantané ne contient pas** : le plan d'engagement du Hub ne détient ni décisions avec alternatives et hypothèses, ni éléments d'architecture, ni liens de conformité, ni journal de réutilisation. [`schemas/engagement_bundle.schema.json`](../../schemas/engagement_bundle.schema.json) reste le modèle cible de ces compléments ; l'instantané n'invente rien.

### 5.19 Contrat 1.19 — Décisions dans la base d'engagement (K16)

Une **décision** enregistre ce que la délibération a engagé : option retenue, **options écartées avec leur raison**, rationale, réversibilité, conséquences, violations acceptées (avec justification), références à la base. Sous les rôles du §5.16, comme les énoncés.

| Route (`/api/engagements/{id}/…`) | Rôle | Effet |
|---|---|---|
| `POST decisions` `{subject, decision, rationale, reversibility, rejected?, consequences?, accepted_violations?, based_on?, supersedes?, origin?}` | `contributor` | **propose** une décision (`201`) ; `Idempotency-Key` comme pour les énoncés |
| `POST decisions/{id}/assert` | `decider` | l'affirme (`active`, `validated_by`, `validated_at`) ; la décision qu'elle remplace devient `superseded` dans le même geste |
| `POST decisions/{id}/withdraw` | auteur ou `decider` | `withdrawn` ; refusé (`409 subject_decided`) si le sujet est décidé sur elle |

Règles : le sujet doit exister (`400`) ; `reversibility` ∈ `reversible, costly, irreversible` ; chaque option écartée a une raison, chaque violation acceptée une justification ; l'option retenue ne figure pas parmi les écartées ; **une seule décision affirmée par sujet** (`409 decision_exists` : nommer l'ancienne dans `supersedes` pour la remplacer ; `409 decision_pending` s'il y en a déjà une proposée) ; **personne n'affirme sa propre décision** (`409 self_validation`) ; un contenu `llm-derived` reste proposé.

**Changement de règle de maturité** : `L3_decided` et `L4_specified` exigent désormais une **décision affirmée** sur le sujet (avant : un énoncé affirmé), toujours sans conflit ouvert (`409 no_asserted_decision`, `open_conflict`).

**Instantané** (`schemaVersion` `1.1`, additif) : `data.decisions` avec `assertion_level` dérivé du statut ; `kb_references` et `unresolved_references` portent `statement_id` **ou** `decision_id`. Vérifications ajoutées : `DECIDED_WITHOUT_DECISION` (sujet `L3`/`L4` sans décision affirmée), `MULTIPLE_ACTIVE_DECISIONS`, `INCONSISTENT_ALTERNATIVES`, `SUPERSESSION`, et les contrôles de personne des énoncés (`ASSERTED_WITHOUT_PERSON`, `SELF_VALIDATION`, `AUTHOR_NOT_A_HANDLE`, `VALIDATOR_ON_PROPOSED`, `DANGLING`).

**Pas dans ce lot** : la conformité exigence → contrôle et G3 dérivés (voir K17) ; une lecture `GET` des décisions (elles sont lues par l'instantané).

### 5.20 Contrat 1.20 — Import d'un engagement depuis un autre système (K12)

Archinex tenait l'engagement ; le Hub est désormais le système d'enregistrement. L'import est fait **par le client qui connaît ses données** ; le Hub le rend sûr et répétable. Action `import` (rôle `admin` seulement, §5.16).

`POST /api/engagements/{id}/import` (`?dry_run=true` ou `"dry_run": true` : **rien n'est écrit**) avec `{batch_id, subjects?, requirements?, statements?, decisions?, questions?, allow_partial?}` ; au plus 2000 éléments. Chaque énoncé, décision et question porte une `key` (idempotence : l'identifiant en dérive, un élément déjà présent est laissé **inchangé**, jamais écrasé).

**Provenance, pas réécriture.** L'auteur (**handle d'un membre**), `created_at`, le valideur et `validated_at` d'origine sont conservés ; chaque élément repris est marqué `imported_from` le lot et `imported: true` dans l'instantané (schéma `1.2`).

**Rien n'est affirmé au nom du lot.** Un élément est `active` seulement si la source nomme un valideur **membre `decider` ou `admin`, distinct de l'auteur**, avec la date ; sinon il est importé `proposed` et signalé (`adjusted`, `no_validator`). Une auto-validation est **rejetée** (`self_validation`).

**Rien n'est réparé en silence.** Rejets (avec `ref`, `kind`, `code`, `path`, `reason`) : `unknown_author`, `validator_not_a_decider`, `validated_at_required`, `status_conflict`, `self_validation`, `email` (adresse dans un texte), `unknown_subject`, `invalid_argument` (confiance hors vocabulaire, `verified` sans preuve, date, statut), `requirement_changed`, `decision_exists`, `decision_pending`, `supersession_inconsistent`. Une maturité `L3`/`L4` que les décisions du lot n'étayent pas est importée à `L2_decomposed` et listée (`maturity_capped`). La détection de conflits tourne à l'application sur les énoncés affirmés ; la simulation ne la rejoue pas.

**Tout ou rien par défaut** : un seul rejet et rien n'est écrit (`422 import_refused`, rapport complet dans `data`) ; `allow_partial` applique les éléments acceptés. Réponse : `{batch_id, dry_run, applied, counts, accepted, unchanged, adjusted, rejected, conflicts_opened?}`.

Les conflits d'Archinex ne sont pas repris (le Hub détecte les siens à l'affirmation) ; les réponses aux questions arrivent comme énoncés.

---

## 4. Oracles & Vecteurs de Test Partagés

Afin de garantir une interopérabilité sans faille entre implémentations Python et TypeScript, les vecteurs de référence suivants sont tenus à disposition dans le dépôt :
* **Vecteur de Test Canonique (`canonical-json v1` + SHA-256)** : [`tests/fixtures/canonical_conformity_vector.json`](../../tests/fixtures/canonical_conformity_vector.json)
* **Jeu d'Essai CCTP de Référence (Messagerie OIV)** : [`fixtures/rfp_messagerie_securisee.txt`](../../fixtures/rfp_messagerie_securisee.txt) (SHA-256: `792b9d332e8ccc589a2d74468d56bc761539542fc8d337a71d77854f87c258b5`)
