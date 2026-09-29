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

## 4. Oracles & Vecteurs de Test Partagés

Afin de garantir une interopérabilité sans faille entre implémentations Python et TypeScript, les vecteurs de référence suivants sont tenus à disposition dans le dépôt :
* **Vecteur de Test Canonique (`canonical-json v1` + SHA-256)** : [`tests/fixtures/canonical_conformity_vector.json`](../../tests/fixtures/canonical_conformity_vector.json)
* **Jeu d'Essai CCTP de Référence (Messagerie OIV)** : [`fixtures/rfp_messagerie_securisee.txt`](../../fixtures/rfp_messagerie_securisee.txt) (SHA-256: `792b9d332e8ccc589a2d74468d56bc761539542fc8d337a71d77854f87c258b5`)
