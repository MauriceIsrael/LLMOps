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
  * `source_system` *(optionnel)* : seule la valeur `knowledge-hub` est acceptée (1.30, K6) ; toute autre valeur est refusée en `400`.
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
        "status": "allocated",
        "evidence": [
          {
            "mode": "architecture-model",
            "type": "graph-item",
            "reference": "ADR-0011",
            "source": "knowledge-hub"
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
Fournit, pour les blocs de prose de `document-engine`, la **doctrine de la base de connaissances qui s'applique** : des extraits cités, pas une rédaction. Elle n'écrit jamais dans le `ProseStore` du compilateur pur et ne dit jamais que la conception du projet est validée ou conforme (le Hub ne connaît pas le projet). Ce n'est pas un canal (ADR-SUITE-05, second amendement, D5) : un appel d'assistance, dont la circulation des données est décrite dans `docs/plans/NOTE-circulation-donnees-assistance-prose.md`. Forme rejouée par `tests/contract/test_prose_suggest_batch_contract.py` et `tests/fixtures/suite/prose-suggest-batch.vectors.json`.

* **Corps de requête** (corrigé le 2026-10-24 : l'exemple précédent n'avait pas suivi le correctif de contenu de §5 « assistance de prose » ; il ne montrait pas `context` et laissait croire que `anchorIds` était lu, et sa réponse affichait la phrase « Conception validée… » que la route ne produit plus) :
```json
{
  "requests": [
    {
      "blockId": "block-gitops",
      "anchorIds": ["gitops-pipeline"],
      "instructions": "Préciser le versionnement des configurations.",
      "context": {"anchoredItems": [{"id": "gitops-pipeline", "attributes": {"label": "GitOps configuration pipeline"}}]}
    }
  ]
}
```
  * **Lu** : `blockId` (chaîne non vide, sinon l'élément est ignoré sans erreur), `instructions` (facultatif), `context.anchoredItems[].attributes.label` (chaînes non vides). La requête adressée à la base est formée de ces libellés et de la consigne.
  * **Reçu mais ignoré** : `anchorIds` et tout autre champ, y compris le reste du `ProseContext`. Le Hub ne les lit, ne les journalise ni ne les conserve (voir la note de circulation).
  * Corps non JSON ou qui n'est pas un objet : `400`. `requests` qui n'est pas une liste : `400`.
* **Réponse HTTP 200** :
```json
{
  "drafts": {"block-gitops": "Connaissances de la base applicables à ce bloc — à reformuler et à valider par l'auteur ; elles ne démontrent pas que la conception du projet s'y conforme :\n- [P-001] … (principe, conçu, à valider) : …"},
  "warnings": [{"blockId": "block-sans-libelle", "message": "Aucun libellé d'élément ancré ni consigne : rien à confronter à la base de connaissances."}],
  "basedOnModelHash": "fa1ecf2b8be24ab7",
  "generatedAt": "2026-10-24T16:00:00Z"
}
```
  * Un bloc n'a **un brouillon que si de la doctrine s'applique** ; sinon **aucun brouillon** et un avertissement `{blockId, message}`. Un bloc n'est jamais à la fois dans `drafts` et dans `warnings`.
  * La confiance est donnée telle que publiée ; `vendor-stated`, `stated-by-client` et `assumed` ne sont jamais présentées comme vérifiées.
  * `basedOnModelHash` est une empreinte **opaque** (16 premiers hex du sha256 de la représentation texte du corps côté Python) : elle ne se rejoue pas hors du Hub. `generatedAt` est l'instant de l'appel.
* **Authentification** : jeton de service (`Authorization: Bearer`), jamais l'identité d'un expert.

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
- Correspondance lexicale sur `title`, `description` et les `statements`, même normalisation que 5.1.1 ; une occurrence précédée d'une négation (`no`, `not`, `without`, `sans`, `pas`…) ne compte pas. Pour une clause `requires`, un terme attendu nié (ex. « sans évaluation de sécurité ») ne satisfait pas la clause et est signalé dans `negated_terms`.
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
       "negated_terms": [], "excerpt": "…", "source_ref": "data/kb/principles/P-002.md", "check_status": "draft"},
      {"typed_id": "control:NIS2-ART21-2A", "check_id": null, "verdict": "unassessed", "message": null,
       "matched_terms": [], "negated_terms": [], "excerpt": "…", "source_ref": "data/kb/controls/NIS2/NIS2-ART21-2A.md", "check_status": null}
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

**Normalisation des candidats issus de la Porte G4 (Archinex)** : `POST /api/knowledge/candidates` accepte également les champs structurés de capitalisation (`summary`, `suggested_change`, `target_asset_ref`, ainsi que `author` / `production_mode` à la racine) lorsque `proposed_content` ou `asset_type` sont omis ou contiennent un identifiant générique (`PAT-000`, `ADR-0000`) :
- `new_asset` et `rex` sont automatiquement enrichis d'un front matter YAML complet (`PAT-xxx` / `ADR-xxxx` libre suivant, `domain` normalisé, `phase`, `assumptions` pour les décisions) et des sections Markdown réglementaires afin d'être directement acceptables et promouvables en doctrine réutilisable ;
- `target_asset_ref` est normalisé vers `target_asset_id` (suppression du préfixe typé `principle:`, `pattern:`, `decision:`, `control:`) et fusionné avec l'actif cible lors d'un `amendment` ;
- les marqueurs de métadonnées de délibération (`COMPLIANCE_STATUS:*`, `PORTABILITY:*`) transmis par erreur comme cible d'amendement sont rejetés explicitement en `400` (`target_asset_id`).

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
- **Détection de conflits** : `CONFLICT_DETECTION_MODE=legacy|strict` (défaut `legacy`, comportement inchangé). `strict` ne signale que des valeurs **différentes** pour un même prédicat ; `legacy` signale aussi deux auteurs qui écrivent la même valeur. Ne pas changer le défaut sans l'accord écrit de l'équipe Archinex. **Une seule définition** (issue #79) : l'intake d'élicitation (`elicit confirm`) et l'affirmation par l'API partagent `ElicitationRepository.run_checks` ; la clause historique de l'intake « auteurs différents sur des prédicats différents » est retirée (deux propriétés distinctes ne se contredisent pas). Sur un engagement **géré**, l'intake écrit des énoncés `proposed` et n'affirme rien (issue #78).

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
| `POST subjects` `{name, definition?, requirement_ids?}` | `contributor` | crée (`201`) ou retrouve (`200`) un sujet ; `requirement_ids` (1.27) : exigences qu'il porte, qui doivent exister |
| `POST subjects/{name}/maturity` `{level}` | `decider` | avance la maturité ; `L3_decided` et `L4_specified` exigent un énoncé **affirmé** sur le sujet et **aucun conflit ouvert** (`409 no_asserted_statement`, `open_conflict`) |
| `POST statements` `{subject, value, confidence, section?, predicate?, role?, verbatim?, based_on?, origin?}` | `contributor` | propose un énoncé, `status: proposed` |
| `POST statements/{id}/assert` | `decider` | l'énoncé devient `active`, avec `validated_by` et `validated_at` ; ouvre les conflits détectés (`conflicts_opened`) |
| `POST statements/{id}/withdraw` | `contributor` (auteur) ou `decider` | `withdrawn` ; un autre contributeur : `403 not_author` |
| `POST questions` `{question, subject?, section?, …}` | `contributor` | question ouverte |
| `POST questions/{id}/answers` `{value, confidence, …}` | `contributor` | énoncé **proposé** lié à la question, qui devient `answered` |
| `POST requirements` `{requirements: [{id, text, section?, category?, criticality?}]}` | `contributor` | 1 à 500 exigences ; un `id` existant avec le même texte est ignoré (`unchanged`), avec un autre texte : `409 requirement_changed` |
| `POST requirements/{id}/disposition` `{disposition, reason?}` | `contributor` | **1.27.** Propose ce que la délibération fait de l'exigence : `deliberated`, `evacuated` (`reason` = le motif) ou `clarification_needed` (`reason` = la question au client), 12 caractères au moins pour les deux dernières. `201` ; le rejeu à l'identique `200` (`created: false`, rien n'est remis à zéro) ; `409 disposition_pending` / `disposition_exists` |
| `POST requirements/{id}/disposition/assert` | `decider` | **1.27.** La décision devient `active` (`validated_by`, `validated_at`) ; refusée à son auteur (`409 self_validation`) et, pour `evacuated` / `clarification_needed`, tant qu'un sujet porte l'exigence (`409 carried_by_subject`) |
| `POST requirements/{id}/disposition/withdraw` | `contributor` (auteur) ou `decider` | **1.27.** `withdrawn` ; l'exigence peut recevoir une autre décision |
| `POST subjects/{name}/requirements` `{add?, remove?}` | `contributor` | **1.27.** Ajoute ou retire des exigences portées par le sujet (idempotent) ; `400 unknown_requirement`, `409 requirement_not_deliberated` |
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

### 5.21 Contrat 1.21 — Faits d'architecture portés par les décisions (K18)

Pour qu'un moteur symbolique (K20) puisse raisonner sur le contenu d'une décision, celle-ci affirme des **faits lisibles par machine**, dans un **vocabulaire partagé** par tous les engagements.

**Vocabulaire** : `data/kb/vocabulary/facts.yaml`, élément de la base de connaissance comme les autres : `version` entière, citable (`knowledgeKey` `vocabulary:facts`), gardé par le registre de versions (K3 : même version, mêmes octets). Chaque clé : `key` (`domaine.nom`), `type` (`int`, `bool`, `enum`, `duration` = nombre entier de secondes), `values` (enum), `min`/`max`, `unit`, `label` FR/EN, `asset` (actif de référence, seulement s'il en existe un). Le vocabulaire figure dans l'instantané scellé de la base, section `fact_vocabulary` `{version, knowledge_ref, content_sha256, keys}`. **Écart assumé** : cette section est scellée par son propre `content_sha256`, **hors** de `payload_sha256`, pour qu'un consommateur qui recalcule le sceau sur les six sections historiques continue de vérifier (ajout rétrocompatible).

**Écriture** : `facts: [{key, value, source_excerpt}]` sur `POST /api/engagements/{id}/decisions` et sur les décisions de l'import (K12). `source_excerpt` (obligatoire) cite le passage de la décision dont le fait est tiré. Refus `400` avec `code` et `argument` (chemin) : `UNKNOWN_FACT_KEY` (clé hors vocabulaire), `FACT_TYPE` (mauvais type, hors énumération, hors bornes ; un booléen n'est pas un entier), `FACT_DUPLICATE`, `FACT_SHAPE`. Rien n'est réparé, rien n'est écrit.

**Un fait ne compte que si sa décision est affirmée** (`active`) : l'affirmation par un `decider` distinct de l'auteur couvre la décision **et** ses faits ; une décision proposée, retirée ou remplacée n'en apporte aucun.

`GET /api/engagements/{id}/facts` (rôle `reader`) : `{vocabulary, items: [{key, value, unit?, source_excerpt, decision, subject}], contradictions: [{key, decisions}]}`. Deux décisions en vigueur qui donnent des valeurs différentes à une même clé sont **signalées** (`contradictions`), jamais départagées.

**Instantané d'engagement** (schéma `1.3`) : chaque décision porte `facts`, et `data.facts` liste les faits en vigueur lus contre le vocabulaire de l'instantané de base épinglé (`pins.kb_snapshot`). L'export est refusé si cet instantané n'a pas de vocabulaire ou ne connaît pas une clé (`fact_vocabulary_missing`, `kb_snapshot_unavailable`) ; la vérification refuse un fait dont la décision n'est pas affirmée, qui n'est pas dans la décision, ou une liste incomplète.

### 5.22 Contrat 1.22 — Règles de déclenchement de questions attachées aux actifs (K19)

Une règle relie des faits affirmés (§5.21) à une question qui devient pertinente. C'est un savoir d'architecte réutilisable : il vit **avec l'élément qui le justifie** (principe, pattern, contrôle), dans la base de connaissance, versionné et citable. Chaque question générée par le moteur (K20) est ainsi traçable jusqu'à une référence de la base.

**Fichier** : `data/kb/triggers/TRG-<nom>.yaml`, une règle par fichier (le nom du fichier est l'identifiant). Choix assumé : la règle est un élément **rattaché par référence** à son porteur (`asset`), et non incorporée à sa page, pour que modifier une règle ne fasse pas monter la révision de l'actif.

| Champ | Contenu |
|---|---|
| `trigger_id`, `version` | identifiant `TRG-…` ; entier ≥ 1, citable `trigger:<id>` (registre de versions, K3) |
| `asset` | le porteur : un élément de la base de connaissance (actif ou contrôle), jamais inventé |
| `when` | **conjonction** de conditions `{key, op, value}` ; `key` du vocabulaire (§5.21) ; `op` ∈ `eq`, `neq`, `gte`, `lte`, `in` |
| `question`, `rationale` | textes `{fr, en}` |
| `initial_level` | `L0_named` ou `L1_framed` |
| `suggested_role` | rôle suggéré |
| `mandatory` | vrai pour un contrôle réglementaire : clore la question exigera une justification. Obligatoire sur une règle portée par un contrôle de sévérité `mandatory` |

**Sémantique figée** (déclaratif, aucun code ; `pipelines.triggers.matches` en est l'évaluation de référence) : une condition n'est vraie que si un **fait en vigueur** existe pour cette clé et que la comparaison tient ; **sans fait, la condition est fausse, `neq` compris** ; `in` tient si la valeur est l'une de la liste ; `gte` et `lte` ne s'appliquent qu'aux clés `int` et `duration` ; un booléen n'est pas un entier.

**Validation** à l'ingestion (`pipelines.cli ingest`, qui s'arrête) et à la publication (export de l'instantané, qui refuse) : clé du vocabulaire, valeur du bon type et dans les bornes, opérateur compatible, porteur existant. Une règle invalide n'est pas publiée ; le rapport donne le fichier, le **chemin** (`when[1].key`) et le code (`UNKNOWN_FACT_KEY`, `VALUE_TYPE`, `OP_TYPE`, `UNKNOWN_OP`, `CONDITION_SHAPE`, `UNKNOWN_ASSET`, `MANDATORY_REQUIRED`, …).

**Instantané de la base** : section `question_triggers` `{items, content_sha256}`, chaque règle avec son `knowledge_ref` (`trigger:<id>`) et son porteur résolu (`carrier`: actif avec `typed_id` et `knowledge_ref`, ou contrôle avec `framework`). **Écart assumé**, comme pour `fact_vocabulary` : la section est scellée par son propre `content_sha256`, **hors** de `payload_sha256` (consommateurs existants intacts). Changer une règle change sa `version` et le sceau de la section, pas le `payload_sha256`.

**Relations du graphe.** Une règle n'a pas de relation propre : elle est portée par un élément, et les relations existantes de cet élément disent ce qu'elle rend pertinent. Exemple : une règle portée par un pattern qui `implements_controls` des contrôles ouvre une question dont les contrôles mis en œuvre sont déjà résolubles depuis `compliance_index` ; retenir le pattern rend ces contrôles pertinents sans les répéter dans la règle. Le moteur (K20) lit la règle ; il ne suit pas les relations.

Jeu initial (six règles) : réplication et RPO (`topology.dc_count ≥ 2`), split-brain à deux sites actifs, bascule du trafic en actif/actif, répartition à trois sites ou plus, souveraineté d'hébergement (SNC-REQ-01, `mandatory`), continuité NIS2 (NIS2-ART21-2C, `mandatory`). Amorçage et revue : K22.

### 5.23 Contrat 1.23 — Moteur de cascade : une décision affirmée ouvre des sujets plus précis (K20)

Le moteur s'exécute **dans le Hub**, sur la base d'engagement, de façon **déterministe et sans modèle de langage** (comme `compliance_mapper`). Chaînage avant interactif : les faits en vigueur de **tout l'engagement** (§5.21, décisions affirmées uniquement) sont lus contre les règles (§5.22) de l'instantané de base **épinglé**. **Le moteur ne déduit jamais de décision** : il ouvre des questions que seuls des humains tranchent.

**Déclenchement.** Après l'affirmation, le remplacement ou le retrait d'une décision (`POST …/decisions/{id}/assert|withdraw`, réponse : clé `cascade` = `{pinned, created, contested, restored}` ou `{skipped}`), après un import (K12), et au changement d'épinglage. `run` est une fonction de l'état, pas des événements : le rejouer ne change rien. Si la base épinglée est inutilisable, l'affirmation réussit et la réponse dit pourquoi (`skipped`).

**Sujet dérivé.** Une règle qui tient ouvre un sujet : nom = identifiant de règle sans `TRG-` (suffixé `-derived` si une personne porte déjà ce nom), définition = la question (`en`), niveau = `initial_level`. `origin: derived`, **valeur que seul le moteur écrit** : aucune route ne la prend d'un appelant. Provenance conservée : `{trigger_id, trigger_version, knowledge_ref, kb_snapshot, facts: [{key, value, decision}], parents: [{subject, decision}], question, rationale, suggested_role, mandatory}`. Un sujet dérivé est une **question, pas une affirmation** : il ne passe pas par la validation distincte.

**Idempotence.** Une règle n'ouvre qu'**un** sujet par engagement (clé `trigger_id` + engagement). Rejouer l'affirmation ou l'import ne duplique rien.

**Maintien de la vérité.** Quand la condition d'une règle ne tient plus (supersession, retrait, règle absente de la base épinglée après un changement d'épinglage), le sujet passe à `foundation_contested` avec la cause : `{unsatisfied: [{key, op, value, current}]}` (`current` nul : plus aucun fait ; `contradiction: true` si la clé est affirmée avec deux valeurs) ou `{rule_missing: true}`. Il n'est **jamais supprimé**. Si la condition redevient vraie, la marque est levée. Une clé affirmée avec deux valeurs par deux décisions en vigueur est **inutilisable** : la condition est fausse, personne n'est départagé.

**Question obligatoire.** Une règle `mandatory` ouvre aussi une question bloquante (`G2_unanswered_blocking`, `section: cascade`). La clore (`POST …/questions/{id}/answers`) exige le rôle `decider` ou `admin` (`403 mandatory_question`) et une `justification` (`400`) ; elle est conservée avec son auteur. Écart assumé : seules les règles `mandatory` créent une question ; les autres sujets dérivés apparaissent comme sujets vides (manque `G1`), la question étant leur définition.

**Base épinglée.** L'identifiant et l'empreinte de l'instantané de base sont fixés à la première dérivation, par engagement. `PUT /api/engagements/{id}/kb-pin` `{snapshot_id}` (action `pin`, rôle `admin`, journalisé) les change ; le moteur réévalue aussitôt. L'export (K11) lit la base épinglée dès qu'elle existe.

**Lecture.** `GET /api/engagements/{id}/lineage` (rôle `reader`) : `{kb_snapshot, pin_unavailable, derived: [...], tree: [{subject, decisions: [{decision, derived: [{subject, rule, version, foundation, facts, children}]}]}]}`. Chaque entrée de `derived` dit si sa règle se résout dans la base épinglée (`resolved`), son état (`sound` ou `foundation_contested`), et le statut de sa question.

**Instantané d'engagement** (schéma `1.4`) : chaque sujet porte `origin` ; section `data.lineage` `{kb_snapshot, items}` (sans date : fonction de l'état). La vérification refuse : un sujet dérivé dont la règle ne se résout pas dans la base épinglée (`DERIVED_RULE_UNRESOLVED`), un sujet dérivé sans lignée ou une lignée sans sujet dérivé, un sujet contesté sans cause, une décision parente inconnue. L'outil MCP sans état `evaluate_cascade` (optionnel dans l'issue) n'est pas livré.

### 5.24 Contrat 1.24 — Ajustements des règles par engagement (K21)

Les règles de référence (§5.22) vivent dans la base de connaissance et ne savent rien d'un programme. Chaque engagement a pourtant ses spécificités : une règle peut y être non pertinente, une règle propre au programme peut manquer. Ces ajustements sont des **éléments engagés** : ils vivent dans la base d'engagement, **jamais** dans la base de connaissance (aucune règle locale n'apparaît dans l'instantané de la base).

**Désactiver une règle de référence** : `POST /api/engagements/{id}/rules/{trigger_id}/disable` `{justification}` (action `decide`, donc `decider` ou `admin`). La **justification est obligatoire** (`400`), règles `mandatory` comprises, et tracée dans le journal d'accès (`rule_disable` : règle, `mandatory`, justification, acteur). La règle doit exister dans la base épinglée (`404 unknown_rule`). Les sujets qu'elle avait ouverts restent, marqués `foundation_contested` avec la cause `{rule_disabled: true}` (K20). `POST …/enable` la réactive (`409 not_disabled` sinon) ; si sa condition tient, le moteur la rouvre.

**Règle locale** : `POST /api/engagements/{id}/rules` (`contributor`) avec le schéma de K19 (`trigger_id`, `version`, `when`, `question`, `rationale`, `initial_level`, `suggested_role`, `mandatory`, `asset` facultatif) et **les mêmes contrôles**, lus contre le vocabulaire et les porteurs de la base épinglée. Écart assumé : l'identifiant est `TRG-local-…` (espace réservé à l'engagement, refusé dans `data/kb/triggers`) et le porteur `asset` est **facultatif** (une règle propre à un programme n'a pas forcément d'élément de la base derrière elle) ; il est vérifié s'il est donné. Elle est **proposée** : elle ne s'applique qu'une fois **affirmée** (`POST …/rules/{id}/assert`, `decider` **distinct de l'auteur**, `409 self_validation` sinon). `POST …/rules/{id}/withdraw` (auteur ou `decider`) la retire ; elle peut être proposée de nouveau. Refus `400` avec `code`, `argument` (chemin, p. ex. `when[0].key`) et `problems`.

**Lecture** : `GET /api/engagements/{id}/rules` : `{kb_snapshot, reference: [{trigger_id, version, mandatory, carrier, disabled, justification}], local: [...]}`.

**Évaluation** : le moteur lit `règles de la base épinglée − désactivations + règles locales affirmées` ; chaque réponse d'écriture porte le rapport `cascade` (K20). Un sujet dérivé d'une règle locale porte `scope: local` et `knowledge_ref` nul.

**Instantané d'engagement** (schéma `1.5`) : section `rule_adjustments` `{disabled: [{trigger_id, mandatory, justification, disabled_by, resolved}], local_rules: [{…règle…, status, assertion_level, author, validated_by, validated_at}]}` et `scope` sur chaque entrée de `lineage`. La vérification refuse : une désactivation sans justification, sans handle, ou d'une règle absente de la base épinglée ; une règle locale affirmée sans personne ou par son auteur, ou proposée avec un valideur, ou dont l'identifiant n'est pas `TRG-local-…`. Une règle locale retirée reste dans la section (comme un énoncé retiré) et ne bloque pas l'export.

**Non livré dans ce lot** : la capitalisation d'une règle locale vers le référentiel par le canal de propositions (K7, K13), après retrait de toute ancre de programme. Elle suivra K7 et K13.

### 5.25 Contrat 1.25 — Recherche sémantique multilingue locale (issue #94)

Le Hub retrouve la doctrine pertinente pour un sujet quelle que soit sa langue : un sujet en français fait remonter un contrôle rédigé en anglais. Il encode lui-même, **localement et sur processeur**, avec `intfloat/multilingual-e5-small` (ONNX int8, 384 dimensions) servi par `fastembed`. Les fichiers du modèle sont téléchargés une fois (`kb models fetch`, ou à la construction de l'image) dans `data/models/`, chacun vérifié contre son SHA-256 épinglé ; **aucun appel réseau à l'exécution**. Sans le modèle, ou avec `KB_EMBEDDINGS=off`, tout se comporte comme en 1.24 (classement lexical).

**Santé** : `GET /health` gagne `embedding {model, version, sha256, dim, local: true, provider: "local", status: "ready"|"absent"|"off", reason}`.

**Contexte de doctrine** (`get_doctrine_context`, `GET /api/knowledge/context`), champs additifs par élément : `relevance` (lexicale, inchangée), `semantic_relevance` (similarité cosinus sujet `query:` / actif `passage:`, ramenée sur [0, 1] par la bande calibrée du modèle ; `null` sans modèle), `combined_relevance` (par défaut `max(lexicale, sémantique)` ; `KB_HYBRID_WEIGHT` = w donne `w × sémantique + (1 − w) × lexicale`), `relevance_method` (`lexical` sans modèle, `semantic` si seul le sens a parlé, `hybrid` sinon) et `relevant`. Un élément est **pertinent** si sa pertinence lexicale atteint 0,2 ou sa pertinence sémantique 0,50 ; parmi les contrôles imposés d'un référentiel déclaré, le plus proche du sujet l'est dès 0,40. Seuls les éléments pertinents entrent dans le paquet, sauf les contrôles imposés, **tous inclus** et triés : priorité de type, pertinents d'abord, score combiné, identifiant. Pour le paquet : `relevance_method` (`lexical` | `hybrid`) et `embedding {model, version, sha256, local}` (ou `null`). Scores arrondis à 4 décimales, un fil ONNX, un texte par passage : même modèle, même base, même sujet ⇒ même ordre. **D9 inchangée** : la pertinence trie, elle ne décide jamais.

**Similarité encodée par le serveur** (`POST /api/knowledge/similar`) : sans `vector`, avec `query_text`, le serveur encode lui-même avec son modèle de référence (les vecteurs des actifs viennent de la table `embeddings`, ou sont encodés en mémoire) ; `scores.vector` est alors la similarité calibrée et `scores.cosine` le cosinus brut ; la réponse porte `encoded_by: "server"|"client"`. Nommer un autre `model` sans `vector` renvoie `409` (`error: "model-mismatch"`, `reference_model`) ; modèle absent : `503`. Le chemin historique (vecteur calculé par le client, comparé aux vecteurs déposés pour **son** modèle) est inchangé.

**Publication** (`kb publish`, `POST /api/knowledge/publications`) : encode les actifs actifs dont le texte a changé (même `text_sha256` : non réencodé), supprime les vecteurs des actifs retirés ou remplacés, et rend `embedding_index {status: indexed|skipped|failed, encoded, unchanged, removed, content_sha256…}` ; un modèle absent n'empêche jamais une publication. `kb embeddings index` fait la même chose sans publier.

### 5.26 Contrat 1.26 — Décision par clause vérifiable (issues #101, #105)

Une clause `checks:` ne devient opposable (elle bloque un arbitrage) que par une **décision explicite sur cette clause** d'un relecteur du domaine de l'actif (ou `kb:maintain`). Accepter un actif entier ne valide jamais ses clauses.

**Format** : chaque clause porte `status` (`draft` | `validated` | `rejected`) et `review {by, at, decision, comment}`. Une clause sans `status` hérite de `checks_status` de l'actif (actifs antérieurs à 1.26). `checks_status` devient l'agrégat : `validated` si toutes les clauses non rejetées le sont, `partial` si certaines, `draft` sinon. Le juge (`check_option`) n'évalue jamais une clause `rejected` ; il rapporte `check_status` de chaque verdict, et seul `validated` bloque côté client.

**Promotion d'un candidat** : une clause identique (`kind`, `when`, `expect`, `message`) à celle de l'actif remplacé garde son statut et sa revue ; toute clause nouvelle ou modifiée est `draft`, quoi qu'en dise le contenu proposé.

**`GET /api/knowledge/checks`** (`kb:review`) — filtres `status`, `framework`, `type`, `asset_id`. Réponse : `clauses[]` (actif : `asset_id`, `typed_id`, `asset_type`, `asset_title`, `asset_title_fr`, `framework`, `severity`, `domain`, `owner`, `source_ref`, `asset_excerpt`, `revision` ; règle : `check_id`, `kind`, `when`, `expect`, `message`, `status`, `review` ; `may_decide` pour l'expert agissant), `counts` par statut, `mandatory_without_clause[]` (contrôles obligatoires actifs sans aucune clause) et `pending_publication` (décisions pas encore publiées).

**`PATCH /api/knowledge/assets/{asset_id}/checks/{check_id}`** (`kb:review`, expert agissant via `X-Actor-Email`, propriétaire du domaine ou `kb:maintain`) — corps `{decision: "validate"|"amend"|"reject", comment?, clause?}`. `amend` valide une clause corrigée (`clause` : `kind`, `when`, `expect`, `message`, champs absents conservés) ; `amend` et `reject` exigent un commentaire. Codes : `200` (la clause après décision), `400` (décision ou clause invalide, commentaire manquant), `403`, `404`. L'actif reçoit une nouvelle `revision` et la décision est ajoutée à `data/kb/clause-decisions.jsonl` (versionné avec la base).

**Effet** : au prochain `POST /api/knowledge/publications` (ou `kb publish`), qui publie aussi quand seules des décisions de clauses sont en attente. La réponse liste `clause_decisions` ; le CHANGELOG les nomme avec leur relecteur.

**Instantané scellé** (D7, D8) : sections `embedding_model {id, version, sha256, dim, local: true, query_prefix, passage_prefix}` et `embedding_index {model, count, items: [{ref, type, text_sha256}], content_sha256}`, hors `payload_sha256`. Elles ne dépendent que de la base et du modèle épinglé (pas de la machine) : le test de fraîcheur (`rebuiltByEmitterTest`) les reconstruit à l'octet.

**Évaluation** : `tests/fixtures/similarity/fr-en-doctrine.yaml` (48 sujets français anonymisés, 8 requêtes anglaises), `make eval-semantic`. Rappel à 5 : 0,90 en hybride contre 0,72 en lexical (français 0,88 contre 0,67 ; anglais 1,00 contre 0,92).

### 5.27 Contrat 1.27 — Décision sur chaque exigence (archinex#34)

**Pourquoi.** Le dossier d'engagement d'Archinex portait, pour chaque exigence d'un appel d'offres, son état (à délibérer, évacuée avec son motif, à clarifier) et le sujet qui la porte. L'instantané du Hub n'avait ni l'un ni l'autre : on ne pouvait pas en tirer une matrice de traçabilité. `schemas/engagement_bundle.schema.json` en version 1.1 est le modèle de contenu ; ce contrat en porte la part **engagée** dans l'instantané du Hub.

**Ce qui est engagé, et ce qui ne l'est pas.** Une exigence **évacuée** par une personne, avec son motif, est un fait engagé : c'est ce qui fonde que rien n'a été écarté sans que l'on sache qui l'a décidé. La **proposition brute d'un modèle**, elle, reste dans le poste de travail : elle n'entre pas au Hub tant qu'un membre ne la propose pas à son nom. « À qualifier » n'est pas une décision, c'est l'absence de décision : elle n'a pas de valeur ici.

**Règles** (celles des décisions, K16) : la décision est **proposée** par un membre (l'auteur est son handle) ; seul un `decider` **autre que l'auteur** l'affirme (`409 self_validation`) ; un `decider` ou l'auteur la retire. Une exigence a au plus une décision en cours (`proposed` ou `active`) ; pour en prendre une autre, on retire la première. Une exigence décidée `evacuated` ou `clarification_needed` n'est portée par aucun sujet : le Hub refuse de l'affirmer tant qu'un sujet la porte, et de la faire porter ensuite.

**Instantané** (`schemaVersion` `1.6`, champs facultatifs) : `requirements[].disposition {value, reason, status, assertion_level, author, validated_by, validated_at}` tant que la décision est proposée ou affirmée (retirée : elle disparaît) et `subjects[].requirement_ids` quand le sujet en porte. Un engagement qui n'utilise ni l'une ni l'autre est scellé **à l'identique**. Rien n'est émis (`verification_failed`) si une décision affirmée n'a pas de personne distincte de son auteur (`ASSERTED_WITHOUT_PERSON`, `SELF_VALIDATION`), si une évacuation n'a pas de motif ni une clarification de question (`DISPOSITION_UNJUSTIFIED`), si une exigence à délibérer n'a aucun sujet (`REQ_UNCOVERED`), si une exigence évacuée ou à clarifier est portée par un sujet (`REQ_NOT_DELIBERATED`) ou si un sujet porte une exigence inconnue (`DANGLING`).

**Hors périmètre.** La conformité (K17), les éléments d'architecture et le journal de réutilisation que le modèle `engagement_bundle` prévoit ne sont toujours pas dans l'instantané : tant qu'ils n'y sont pas, Archinex garde son dossier pour les documents qui en ont besoin (OSCAL, vues d'architecture).

### 5.28 Contrat 1.28 — Explorateur de doctrine complet et historique d'actif (issues Archinex #95, LLMOps #108)

Le Hub permet la reconstitution exhaustive de la traçabilité de la doctrine opposable : chaque actif actif dispose d'un chemin d'entrée (`entry_path`), d'une date initiale d'introduction, de relecteurs/valideurs, de l'historique de ses révisions successives et des décisions portées sur ses clauses. Les référentiels réglementaires tracent leurs textes ingérés d'origine avec version et SHA-256.

**`GET /api/knowledge/publications`** — Liste chronologique des publications scellées avec filtres optionnels `entry_type` (`framework_ingestion`, `doctrine_workshop`, `amendment`, `initial_baseline`) et `framework`.
Réponse :
* `publications[]` : `snapshot_id`, `created_at`, `entry_path`, `source` (`framework`, `version`, `sha256`, `file_name`), `reviewers`, `added[]`, `revised[]`, `removed[]`, `summary`, `clause_decisions[]`.
* `count` : nombre de publications retournées.

**`GET /api/knowledge/assets/{asset_id}/history`** — Historique des révisions et chaîne de traçabilité pour un actif donné.
Réponse :
* `asset_id` : identifiant de l'actif.
* `initial_date` : date ISO de publication initiale.
* `initial_snapshot` : identifiant de l'instantané scellé initial.
* `entry_path` : vecteur d'entrée initial de l'actif (`framework_ingestion`, `doctrine_workshop`, `amendment`, `initial_baseline`).
* `source` : métadonnées de source (`framework`, `version`, `sha256`).
* `validators` : relecteurs et experts ayant validé ou promu l'actif.
* `revisions[]` : liste chronologique des révisions (`revision`, `date`, `snapshot_id`, `author`, `reviewers`, `change_summary`, `content_sha256`).
* `clause_decisions[]` : historique des décisions prises sur les clauses de l'actif (#105).

**`list_frameworks`** : chaque référentiel s'enrichit de `ingested_source`, `source_sha256` et `associated_publications` listant les instantanés scellés contenant des contrôles de ce référentiel.

### 5.29 Contrat 1.29 — Amorçage et revue des règles de déclenchement (K22)

Les règles (§5.22) et les clés du vocabulaire (§5.21) entrent dans la base de connaissance par le **même cycle que toute connaissance** (§5.2) : candidat, contrôles déterministes, revue humaine, promotion, publication (§5.8). Rien n'est publié automatiquement, quelle que soit l'origine.

**Deux types de candidat** (`asset_type`) : `trigger` (le contenu est le YAML d'une règle ; amendement : `target_asset_id` est la règle et `version` vaut la précédente + 1, exigé par le registre de versions, K3) et `fact_key` (le contenu est le YAML d'une clé ; l'accepter ajoute la clé et fait monter la `version` du vocabulaire ; le type d'une clé existante ne change pas). `source.system` accepte `kb-extraction`. Le contrôle `schema` est **le validateur de K19** sur le vocabulaire courant : une clé inconnue fait échouer le candidat (`checks_failed`) avec le chemin de la clé ; `anonymization`, `llm_unreviewed` et `previously_rejected` s'appliquent comme aux autres candidats ; `references`, `duplicate` et `doctrine_conflict` (faits pour du Markdown) ne s'appliquent pas.

**Extraction** : commande hors ligne `kb extract-triggers [--asset ID] [--dry-run]` (comme `kb suggest-links` : seul endroit où un modèle est utilisé, jamais sur une route servie ; ignorée sans `LLM_ENDPOINT`). Elle lit les sections « Consequences », « Trade-offs », « Implications », « When not to use this », « Revisit when » (et leurs équivalents français) des principes, patterns et décisions actifs. Sortie **contrainte** : une règle est validée par le validateur de K19 ; la phrase citée (`source_quote`) doit figurer **mot pour mot** dans la section lue, sinon la proposition est écartée et signalée ; une clé inconnue doit être **définie** par le modèle (`new_keys`) et devient un candidat `fact_key` à revoir, la règle restant `checks_failed` tant qu'une personne n'a pas accepté la clé, ou fusionné, ou amendé. Tout est `llm-derived`, passage cité dans `rationale`. Rejouer ne crée rien de ce qui existe (règle, clé, candidat en cours).

**API de revue** (application d'administration) :

| Route | Rôle |
|---|---|
| `GET /api/knowledge/triggers` | `{vocabulary, assets: [{id, title, rules}], candidates}` ; la file `candidates` (règles et clés en cours de revue, avec leur contrôle `schema`) est réservée au scope `kb:review` |
| `POST /api/knowledge/triggers/validate` `{content, asset_type?, target_asset_id?}` | validation en direct : `{valid, problems: [{path, code, reason}]}`, **même validateur** que le contrôle `schema` et la publication ; rien n'est stocké |
| `POST /api/knowledge/triggers/preview` `{facts: {clé: valeur}, rules?: [YAML ou objet]}` | « avec ces faits, voici les questions qui s'ouvriraient » : `{opens, closed: [{trigger_id, unsatisfied}], invalid_drafts}`. Les faits sont validés sur le vocabulaire (`400`, `code`, `path`) ; `rules` ajoute des brouillons (un candidat en revue) aux règles de référence |
| `POST /api/knowledge/candidates/{id}/merge-key` `{into, reviewer, reason?}` | scope `kb:review` : rejette le candidat `fact_key` (le motif consigne la fusion) et renvoie les règles candidates qui citent la clé, chacune avec son contenu réécrit sur la clé existante ; le relecteur les amende ensuite (une règle n'est jamais modifiée ni acceptée par effet de bord) |

L'aperçu et le moteur de cascade (§5.23) utilisent **la même évaluation** (`pipelines.triggers.evaluate`) : mêmes faits, mêmes règles, mêmes questions (test de recette). La revue elle-même (accepter, amender, rejeter) passe par `PATCH /api/knowledge/candidates/{id}` (§5.2), la promotion et la publication par §5.8.

**Application d'administration** (`apps/kb-client-app`, `/governance/triggers`) : liste des règles par actif, file des candidats, éditeur avec validation en direct, aperçu, actions accepter, amender, rejeter et fusion de clé, appuyés sur ces routes (proxy `api/kb/triggers`, jeton `LLMOPS_REVIEW_TOKEN`). **Vérifiée par `svelte-check` et par le build, non validée visuellement.**

### 5.30 Contrat 1.30 — Snapshot de conformité honnête (K6, issue #43)

**Pourquoi.** Le Hub « ne détient ni résultat de vérification, ni preuve » (ADR-KH-01 D2). Or `GET /api/compliance/conformity-snapshot` marquait `verified` toute exigence dont un actif du graphe était référencé (une **présence** devenait un **résultat de vérification**), étiquetait ses preuves `architecture-studio`, et laissait l'appelant choisir `sourceSystem`.

**Ce qui change** (comportement corrigé, sans changement de forme) :

* `status` vaut `allocated` (couverture **déclarée**, non vérifiée) ; aucun chemin du Hub n'émet `verified`.
* Les preuves portent `source: "knowledge-hub"` (leur vraie origine).
* `sourceSystem` est fixé à `knowledge-hub` ; `?source_system=` (ou `X-Source-System`) avec une autre valeur est refusé : `400 {"status": "invalid_argument"}`. L'ancienne valeur `tuleap` n'est plus servie.
* **Correction (contrat 1.40) :** cette ligne affirmait que le consommateur (`validateConformitySnapshot` du Document Engine) « accepte toujours l'enveloppe ». C'est inexact : voir §5.40 pour ce qu'il refuse, mesuré.

La couverture exigence → contrôle d'un **engagement** (décisions affirmées) est l'objet de K17 (§5.31), dans l'instantané d'engagement, pas dans cette route.

### 5.31 Contrat 1.31 — Couverture exigence → contrôle dans l'instantané d'engagement (K17, issue #65)

**Pourquoi.** Le bundle d'Archinex portait une matrice de conformité ; l'instantané du Hub n'en avait pas (écart de parité, archinex#34). Le Hub la calcule désormais, de façon **déterministe et déclarative** : il ne vérifie rien (D2, K6).

**Section `compliance`** (instantané d'engagement, `schemaVersion` `1.7`, additif) : `{origin, kb_snapshot, items, unresolved}`.

* Pour chaque exigence de l'engagement et chaque contrôle auquel elle a été rapprochée (`matched_controls`, résolu dans la base de connaissance **épinglée**), une ligne `{requirement_id, control_id, framework, severity, status, decisions, assets}`.
* `status` : `allocated` si une décision **affirmée** cite le contrôle ou un actif qui le met en œuvre (`based_on`) ; `proposed` si seule une décision proposée le fait ; `uncovered` sinon. Une décision retirée ou remplacée ne couvre rien.
* Une exigence **évacuée** par une décision affirmée n'est pas délibérée : aucune ligne. Un contrôle que la base épinglée ne connaît pas est listé dans `unresolved`, jamais inventé.
* `verified` n'existe pas ; `origin` vaut toujours `knowledge-hub` (le schéma n'admet pas d'autre valeur).

**Vérification** : un statut que les décisions citées ne soutiennent pas est refusé (`COVERAGE_STATUS`), ainsi que toute référence pendante (`DANGLING`). Abaisser une décision de « affirmée » à « proposée » change la couverture et le checksum.

Les manques G3 `principle_unaddressed` ne sont pas inclus : ils demandent une règle d'applicabilité des principes que la doctrine ne porte pas encore.

### 5.32 Contrat 1.32 — Étanchéité de la capitalisation (K13, issue #51)

**Pourquoi.** La base de connaissance est agnostique de tout programme (ADR-KH-01 A10-d-3) : une décision de projet n'y entre que par un candidat revu par un humain, et rien ne doit permettre de remonter à l'engagement d'origine.

**Une seule définition d'une ancre de programme** (`pipelines/kb_candidates/anchors.py`), partagée par le contrôle `anonymization` du cycle des candidats et par le `subject_label` du journal de réutilisation :

* l'**identifiant d'un engagement** (les engagements enregistrés, les bases de travail présentes, et celui dont vient le candidat) ;
* une **adresse e-mail** (masquée dans le résultat : `j***@domaine`), un **handle de membre** (`@nom`, cherché dans le titre, la justification et le corps ; le front matter, où la promotion consigne les relecteurs de la base, en est exclu), une **adresse IP ou CIDR** (plages de documentation admises), un **nom interdit** (liste `anonymization_denylist.txt`) ;
* les champs de front matter `source_engagement`, `engagement`, `engagement_id`, `client`, `site`.

**Effet.** Une ancre fait échouer le contrôle (`checks_failed`, jamais `in_review`) et le message nomme précisément ce qui a été trouvé : le relecteur voit ce qui est refusé. Une confirmation de réutilisation dont le libellé contient une ancre est refusée en `400` et n'écrit rien dans le journal. Les **hypothèses** et la provenance générique (rôle, pas personne) du candidat sont conservées.

**Vérification continue.** Un test parcourt la base de connaissance et échoue si l'identifiant d'un engagement connu y apparaît. PAT-008, qui portait encore `source_engagement` et le nom d'un projet, est nettoyé (révision 2).

### 5.33 Contrat 1.33 — Canal de propositions suite → Hub (K7, issue #44)

**Pourquoi.** L'amendement KH-1 d'`ADR-SUITE-05` interdit à la suite d'appeler le Hub (ni RPC, ni HTTP, ni MCP) : elle **publie** un instantané scellé, le Hub le **lit**. Aucun canal ne disait comment une application de la suite propose de la connaissance au Hub ; `POST /api/knowledge/candidates` aurait violé l'amendement.

**Instantané de propositions** (`schemas/proposal_snapshot.schema.json`, exemple `schemas/examples/proposal_snapshot.example.json`) : enveloppe de la suite `{schemaVersion, snapshotId, sourceSystem, createdAt, checksum, data}`, scellée au profil canonical-json v1 (`checksum` = sha256 de `data`). `sourceSystem` ∈ `document-studio`, `architecture-studio`, `requirements-intake` (le Hub n'est pas un émetteur de propositions). `data.candidates[]` reprend le type `ExtractedCandidate` de la suite (`id`, `sourceFragment`, `suggestedDestination: "knowledge-hub-reference"` obligatoire…) et porte la proposition elle-même dans `proposal {kind, asset_type?, title, rationale?, proposed_content, target_asset_id?, domain?, production_mode?}` (**le schéma de la suite exige `originalText` et `normalizedText` ; le Hub les lit comme facultatifs**, et `proposal` n'appartient pas au schéma de la suite, qui le retire à la lecture : voir `docs/contracts/proposals-emitter-guide.md`) (`production_mode` vaut `llm-derived` par défaut : une proposition extraite n'est pas relue).

**Lecture par le Hub** :

* `kb import-proposals <fichier> [--dry-run]` ;
* `POST /api/knowledge/proposals/import` (corps = l'enveloppe ; `?dry_run=1`) pour les clients qui portent le fichier (Archinex, outils internes), pas pour la suite, qui publie.

**Garanties.**

* L'instantané est vérifié **en entier** (schéma, sceau, identifiants uniques, amendement avec cible) et refusé en bloc sinon : `400`, `problems [{code, path, message}]`, aucun candidat créé (`SEAL` si le contenu a été altéré).
* Chaque proposition devient un candidat du cycle ordinaire (contrôles automatiques dont l'anonymisation K13, revue par le propriétaire du domaine, double validation) : **rien ne devient actif sans revue humaine**.
* Provenance sur le candidat : `source.system` (l'émetteur), `source.snapshot_id`, `source.snapshot_checksum`, `source.candidate_ref` (le candidat dans l'instantané). `source.system` accepte désormais `architecture-studio` et `requirements-intake`.
* **Idempotent** : relire le même instantané ne crée rien deux fois (`skipped`).

Réponse `201` : `{snapshot, dry_run, imported: [{candidate_ref, id, status}], skipped: [...], refused: [{candidate_ref, argument, reason}]}`.

### 5.34 Contrat 1.34 — Capitalisation d'une règle locale (K21 point 4, issue #70)

Une règle locale utile (§5.24) peut remonter vers le référentiel, **par le canal de propositions (§5.33), jamais par un `POST` direct**, et sans rien qui rattache la règle au programme (§5.32).

`POST /api/engagements/{id}/rules/{trigger_id}/capitalise` — rôle `decide` ; corps `{asset}` : l'élément de la base de connaissance qui portera la règle (une règle de référence vit avec un actif ; la règle locale n'en a en général pas). Réponse `200` : `{snapshot, proposed_as, next}` où `snapshot` est l'**instantané scellé de propositions** du canal K7 (`sourceSystem` `hub-engagement`, un candidat `asset_type: trigger`, `production_mode: human-authored`). Un responsable de la base le lit avec `kb import-proposals` ; une personne relit ensuite le candidat.

* Seule une règle **affirmée** est proposée (`409 not_asserted`).
* `TRG-local-x` devient `TRG-x` (`409 id_taken` si ce nom existe déjà dans la base épinglée) ; l'auteur, le validateur et l'engagement ne figurent pas dans une règle.
* La règle est validée comme une règle de référence (vocabulaire K18, porteur) ; un texte libre qui porte encore une ancre de programme (identifiant d'engagement, handle, e-mail, IP, nom interdit) est **refusé et nommé** : `409 anchors_found`.
* Le même instantané est produit pour la même règle : le lire deux fois ne crée qu'un candidat. L'opération est tracée dans le journal d'accès de l'engagement (`rule_capitalise`).

Le canal accepte désormais `asset_type` `trigger` et `fact_key`, et l'émetteur `hub-engagement`.

---

### 5.35 Contrat 1.35 — Couverture exigence → contrôle déclarée par la chaîne des décisions (K17, issue #123)

**Pourquoi.** La couverture du contrat 1.31 ne produit une ligne que pour un contrôle *rapproché* de l'exigence (`matched_controls`). Seules les exigences ingérées par le dépeceur de RFP du Hub portent ce rapprochement : une exigence créée par l'API d'écriture (la voie d'Archinex) n'en a pas, et la section restait vide, quoi que les décisions citent.

**Ce qui est ajouté.** Des lignes que **aucun appariement de texte ne produit**, tirées de la chaîne que l'engagement déclare lui-même :

> exigence ← portée par ← sujet ← décidé par ← décision → cite (`based_on`) → actif de la base → met en œuvre → contrôle

L'exigence est portée par le sujet (1.27), la décision est celle de ce sujet et cite l'actif (ou le contrôle lui-même), et l'instantané de connaissances **épinglé** dit que l'actif met en œuvre le contrôle. Une telle ligne a `basis: "declared_by_decision"` ; elle n'est **jamais `uncovered`** (une décision la soutient) : `allocated` si une décision **affirmée** la soutient, `proposed` si seules des décisions proposées le font. Abaisser une décision d'affirmée à proposée change la ligne et le sceau.

**Ce qui ne change pas.** Les lignes issues de `matched_controls` sont inchangées (même contenu, pas de `basis`) ; un couple déjà rapproché garde sa ligne unique. Une exigence évacuée par une décision affirmée n'a aucune ligne. Aucune route n'est ajoutée ni modifiée ; le schéma de l'instantané passe à `1.8` (champ facultatif `basis`).

**Une correction au passage.** Une clé typée dans `based_on` (`decision:ADR-0001`) est lue comme l'actif qu'elle désigne, pour les lignes rapprochées comme pour les lignes déclarées : auparavant elle ne couvrait rien, faute d'être comparée à l'identifiant nu des actifs qui mettent le contrôle en œuvre.

**Vérification.** Une ligne `declared_by_decision` sans décision (`COVERAGE_WITHOUT_DECISION`), dont une décision n'est pas sur un sujet qui porte l'exigence (`COVERAGE_NOT_CARRIED`), ou un couple exigence / contrôle en double (`COVERAGE_DUPLICATE`) fait refuser l'export.

### 5.36 Contrat 1.36 — Veille réglementaire, matching multilingue FR/EN et indicateur d'angles morts RFP (issues #127, #131, #132, #133)

**1. Correction K17 : Vérification du sujet porteur sur les contrôles rapprochés (Issue #127)**
- Pour les lignes de conformité issues d'exigences rapprochées (`matched_controls`), une décision ne couvre désormais l'exigence que si le sujet de la décision porte effectivement l'exigence (`d["subject"] in req_subjects`).
- L'export scellé d'engagement vérifie systématiquement la règle `COVERAGE_NOT_CARRIED` sur l'ensemble des lignes de conformité (`basis: "matched"` comme `basis: "declared_by_decision"`).

**2. Veille de fraîcheur réglementaire et doctrine KB (Issue #131)**
- `GET /api/knowledge/freshness` (requiert le scope `kb:review`) et outil MCP `get_kb_freshness(framework?, owner?, days=180)`.
- Détecte les revues documentaires échues (`overdue_reviews`), les dérives de versions et de checksums des référentiels amont (`source_drifts`), ainsi que les doctrines dépendantes devant être réévaluées.
- Intégration CLI `kb check-freshness` et `kb freshness-report`.

**3. Évaluation sémantique et matching multilingue FR/EN (Issue #132)**
- Enrichissement du glossaire bilingue (`data/kb/glossary/synonyms.yaml`) avec le vocabulaire technique télécom, résilience et sécurité (`holdover`, `jamming`, `anti-spoofing`, `sepp`, `back-up room`, `four-eyes`, etc.).
- Fonctions d'extension de termes et de clauses : `expand_terms` et `expand_clause_terms`.
- Évaluation inter-langues déterministe (options rédigées en français contre clauses en anglais et vice-versa).

**4. Indicateur d'angles morts de couverture KB sur un appel d'offres (Issue #133)**
- `POST /api/rfp/coverage-gaps` et `GET /api/rfp/coverage-gaps` (outil MCP `get_rfp_coverage_gaps(engagement, rfp_text?)`).
- La matrice de conformité produite par `build_compliance_matrix` inclut désormais le bloc `coverage_gaps`.
- Synthèse des angles morts (`blind_spots`) par section et catégorie thématique, identification des lacunes critiques (`critical_gaps`), et recommandations de référentiels et domaines à ingérer.

### 5.37 Contrat 1.37 — Authentification des experts, assertions signées EdDSA et RBAC fin pour la gouvernance KB (Issue #7)

**1. Assertion d'acteur cryptographique EdDSA (Ed25519) et registre JWKS**
- Ajoute l'assertion signée asymétrique (`X-Actor-Token` ou `X-Actor-Assertion`) émise par Archinex ou un IdP de confiance. **L'en-tête brut `X-Actor-Email` reste accepté par défaut** (jeton portant `kb:delegate` ou `eng:delegate`) : tant que le mode strict du §5.39 n'est pas activé, un jeton de service compromis peut se faire passer pour n'importe quel expert, et la séparation des tâches ci-dessous ne vaut que si l'identité est authentifiée.
- Publication des clés publiques au format RFC 8037 (`OKP` / `Ed25519`) sur le point d'accès standard `GET /.well-known/jwks.json`.
- Vérification cryptographique dynamique (`ActorAssertionVerifier`) avec extraction sécurisée de l'identité (`handle`, `email`), des rôles globaux (`roles`), des rôles restreints par domaine (`domain_roles`) et des délégations (`delegation`).

**2. Protection anti-rejeu et révocation immédiate**
- Chaque assertion d'acteur porte obligatoirement un identifiant unique `jti` (anti-rejeu). Toute tentative de réutilisation d'un même `jti` avant expiration est rejetée avec un code HTTP 403 (`replay_detected`).
- Révocation immédiate disponible via l'endpoint REST `POST /api/knowledge/auth/revoke` (outil MCP `revoke_kb_auth`) : révocation de jeton par `jti` ou exclusion administrative par `handle` ou `email` d'expert (`token_revoked`).

**3. RBAC fin et cycle de vie des délégations temporaires**
- Rôles par périmètre/domaine : attribution de privilèges de revue (`kb:review`) ou d'évaluation (`kb:evaluate`) restreints à des motifs hiérarchiques (`architecture/*`, `security/*`).
- Gestion des délégations temporaires avec date de fin obligatoire (`expires_at`) :
  - `GET /api/knowledge/delegations` (outil MCP `list_kb_delegations`)
  - `POST /api/knowledge/delegations` (outil MCP `create_kb_delegation`)
  - `POST /api/knowledge/delegations/{delegation_id}/revoke` (outil MCP `revoke_kb_delegation`)
- Un expert ne peut déléguer que des domaines qu'il possède dans le registre `domain_owners` ou s'il détient le rôle `kb:maintain`.

**4. Séparation stricte des tâches (Separation of Duties)**
- Règle formelle : l'auteur d'un candidat ne peut ni réviser ni auto-valider sa propre contribution.
- Le rejet `separation_of_duties` (réponse réelle : HTTP 400, `status: invalid_argument`, `argument: reviewer`, `reason` commençant par `separation_of_duties:`) est levé si le `reviewer` tente d'émettre une action (`accept`, `amend`, `reject`) sur un candidat dont il est l'auteur (`handle` ou adresse e-mail concordante).

**5. Journal d'audit d'accès et de gouvernance**
- Table dédiée `kb_access_audit` traçant chaque opération de gouvernance (`login`, `review`, `delegation`, `revocation`) avec l'acteur, le résultat (`allowed`, `denied`), la ressource et l'empreinte `jti`.
- Consultation via `GET /api/knowledge/audit` (outil MCP `get_kb_audit`, requiert le scope `kb:review`).

### 5.38 Contrat 1.38 — Fiabilité du juge : contrôles imposés jamais coupés, cohérence du graphe compilé (issues #106, #85)

Évolution **additive** (aucun champ retiré ni renommé).

**1. `GET /api/knowledge/context` / `get_doctrine_context` — les contrôles imposés ne sont jamais coupés (#106)**
- Tous les contrôles actifs des référentiels listés dans `frameworks` sont renvoyés, quelle que soit la valeur de `max_items`. Le plafond ne s'applique qu'au reste de la doctrine (principes, motifs, décisions, autres contrôles) : le nombre d'éléments renvoyés peut donc dépasser `max_items`.
- Pour tenir `max_chars`, l'extrait d'un contrôle imposé est raccourci (jusqu'à être vide si le budget est plus petit que le nombre de contrôles), jamais le contrôle retiré : il reste avec son identifiant et son titre. Le total des extraits ne dépasse pas `max_chars`, et `truncated` vaut `true` dès qu'un extrait est coupé.
- Champs ajoutés dans `data` : `required_total` (entier, nombre de contrôles imposés) et `omitted_required` (liste d'identifiants typés manquants, **toujours vide** : un client peut le vérifier plutôt que de se fier à la garantie).
- Changement de comportement assumé : avant 1.38, 20 éléments au plus étaient renvoyés par défaut, et au-delà de 20 contrôles imposés, le classement choisissait ceux qui restaient (28 sur 48 perdus avec CRA et NIS2). Un client qui contournait cela avec `max_items=120` n'a rien à changer.

**2. `GET /api/knowledge/health` / `get_kb_health` — le graphe compilé décrit-il les fichiers ? (#85)**
- Le juge lit ses clauses dans le graphe compilé (`data/knowledge.lbug`), pas dans `data/kb/**/*.md`. Chaque actif du graphe porte désormais l'empreinte du **fichier entier** dont il vient (`file_sha256`, front matter compris, indépendante des fins de ligne).
- Champ ajouté : `compiled_base` (objet, ou `null` si le contrôle n'a pas pu s'exécuter) : `status` (`ok` | `stale` | `unverified`), `files`, `assets_in_base`, `changed_since_build`, `not_in_base`, `removed_from_files`, `unverified` (chacun `{count, ids}`), et `reason` hors `ok`. `stale` : un fichier a changé, a été ajouté ou retiré depuis la construction du graphe ; `unverified` : le graphe a été construit avant ce contrat et ne peut pas être comparé.
- Le serveur écrit un avertissement au démarrage dans les deux cas. **Il ne reconstruit jamais le graphe** : un maintainer le décide.
- Ligne de commande : `kb check [--strict] [--json]` (code 1 si `stale` ; avec `--strict`, aussi si `unverified`). Le graphe versionné (`data/knowledge.lbug`) doit être reconstruit avec les fichiers à chaque publication : un test d'intégration échoue s'il est `stale`, et se saute (avec le message de reconstruction) tant qu'il est `unverified`, c'est-à-dire construit avant cette empreinte.

### 5.39 Contrat 1.39 — Identité et droits des personnes qui agissent (Issues #144, #90, #91)

Aucune route n'est ajoutée ; les réponses existantes gardent leur forme. Ce qui change est observable : un refus 401 de plus, une borne sur la durée des assertions, une autorisation de plus sur la déclaration de couverture, une 409 de plus à l'application d'une ingestion.

**1. Mode strict d'identité (`LLMOPS_REQUIRE_SIGNED_ACTOR`, issue #144)**
- Variable d'environnement (ou `.env`) : `true`/`1`/`yes`/`on` l'active. **Absente = mode par défaut** : `X-Actor-Email` reste accepté, comme en 1.4 à 1.37 (serveur de contrat, clients qui ne signent pas encore).
- Activé, une requête qui nomme sa personne par `X-Actor-Email` **sans** assertion est refusée : `401 {"status":"unauthorized","error":"signed_actor_required","reason":…}`. Le refus est écrit dans le journal d'audit (`GET /api/knowledge/audit`, `outcome: denied`, `auth_method: header`, `detail.code: signed_actor_required`).
- Si une assertion valide accompagne l'en-tête brut, **l'assertion seule** désigne la personne ; l'en-tête est ignoré. Les requêtes sans personne (lectures par jeton de service, `/health`, `/.well-known/jwks.json`) sont inchangées.
- Cela couvre aussi les écritures d'engagement (`eng:delegate`) : l'adresse e-mail qui désigne le membre vient de l'assertion (claim `email`).
- Au démarrage, le serveur écrit dans le journal (`mcp_server.identity`) le nombre de clés de confiance ; en mode strict sans aucune clé il écrit une **erreur explicite** et chaque requête signée est refusée en `unknown_key`.

**2. Clés publiques de confiance**
- `ARCHINEX_JWKS` : le JWKS lui-même (`{"keys":[…]}`, clés `OKP`/`Ed25519` avec `kid`).
- `ARCHINEX_JWKS_FILE` : chemin d'un fichier JWKS (un fichier remplacé est relu).
- `ARCHINEX_JWKS_URL` : URL d'un JWKS (`https`, ou `http` sur boucle locale). Mise en cache 300 s ; relu au plus toutes les 30 s, et immédiatement quand un `kid` est inconnu (rotation). **Échec fermé** : une source illisible n'apporte aucune clé ; si l'URL reste injoignable au-delà de 300 s, ses clés ne sont plus de confiance.
- Un `kid` nommé mais non déclaré est refusé : `401 unknown_key` (le message nomme les trois variables). Il n'y a plus de repli sur « la seule clé enregistrée » quand un `kid` est donné.

**3. Format et durée de vie d'une assertion**
- JWT compact, algorithme `EdDSA` (Ed25519) uniquement, en-tête `{"alg":"EdDSA","kid":"<kid déclaré>"}`.
- Claims obligatoires : `iss` (défaut `archinex`, `ARCHINEX_ISSUER`), `aud` (défaut `knowledge-hub`, `ARCHINEX_AUDIENCE`), `sub`, `exp`, `jti` (unique par assertion). Attendus : `iat`, `nbf`, `email` (adresse de la personne : sans elle une écriture d'engagement n'a pas de membre), `handle` (facultatif ; sinon déduit du registre des experts). Facultatifs : `roles`, `domain_roles`, `delegation`.
- Durée de vie `exp − iat` au plus **900 s** (`ARCHINEX_ASSERTION_MAX_TTL`) : au-delà, `401 lifetime_too_long`. Valeur recommandée à l'émission : 300 s.
- Tolérance d'horloge sur `iat`/`nbf`/`exp` : **30 s** (`ARCHINEX_CLOCK_SKEW`). Un `jti` est retenu jusqu'à `exp` + la tolérance.
- Rappel des refus : `invalid_signature`, `invalid_algorithm`, `token_expired`, `invalid_issuer`, `invalid_audience`, `missing_jti` (401) ; `replay_detected`, `token_revoked` (403).

**4. Déclarer un référentiel couvert (`POST /api/frameworks/{fw}/coverage-declaration`, issue #90)**
- Il fallait seulement un expert enregistré. Il faut maintenant le **propriétaire du domaine principal** du référentiel, ou `kb:maintain`, ou le rôle de revue sur ce domaine (`domain_roles` d'une assertion, délégation active). Sinon `403 unauthorized` avec le domaine dans `reason`.
- Domaine principal : `primary_domain` du référentiel dans `data/kb/controls/frameworks.yaml` s'il y est ; sinon le premier domaine que listent le plus de contrôles du référentiel (égalité : ordre alphabétique). Un référentiel sans contrôle n'a pas de propriétaire : un mainteneur seul peut le déclarer.
- Chaque décision (autorisée ou refusée) est écrite dans le journal d'audit (`action: declare_framework_coverage`, `resource: <référentiel>`) ; le déclarant reste dans `coverage_declared_by`.

**5. Appliquer une ingestion de référentiel (`POST /api/frameworks/ingestions/{id}/apply`, issue #91)**
- Le mainteneur qui applique ne peut pas être celui qui a **décidé** (`accept` ou `amend`) un contrôle `severity: mandatory` (sévérité absente = obligatoire). Ces lignes ne sont pas appliquées et restent `decided` : `failed[]` les nomme avec `separation_of_duties:`. Si aucune ligne ne peut être appliquée, la réponse est `409` (`invalid_argument`, `conflict: true`). Un autre mainteneur peut les appliquer. Les rejets (`reject`) et les contrôles non obligatoires ne sont pas concernés.
- `kb apply-review <fichier>` (ligne de commande) n'a pas de personne authentifiée pour appliquer : la règle n'y est **pas** vérifiée.

**Limites connues** : le registre anti-rejeu (`jti`) est en mémoire, par processus : plusieurs processus ou un redémarrage ouvrent une fenêtre de rejeu de la durée de l'assertion. Les `roles` d'une assertion s'ajoutent à ceux du registre pour une personne **connue** : celui qui signe (Archinex) répond de ce qu'il affirme. Une personne **absente du registre des experts** n'a aucun rôle (pas de `kb:review` par défaut) : ses claims `roles` et `domain_roles` sont ignorés, elle n'est pas présentée comme un expert (`GET /api/knowledge/me` → 403 « not a registered expert », comme avec l'en-tête brut), elle reste identifiable pour l'audit sous l'étiquette `email:<adresse>` (celle que donne l'en-tête brut à une adresse inconnue : aucun handle n'est inventé) et, par son e-mail, pour l'appartenance à un engagement. Le réglage `LLMOPS_ASSERTION_ROLES_FOR_UNREGISTERED=true` (éteint par défaut) fait croire les claims d'une personne inconnue, pour un fournisseur d'identité qui gère ses propres personnes.


### 5.40 Contrat 1.40 — Snapshot de conformité honnête et reproductible (Issues #148, #149)

Aucune route n'est ajoutée ; la forme (`schemaVersion` `2.0`) ne change pas. Deux comportements changent, et le contrat dit enfin ce que le consommateur fait de la sortie.

**1. Identifiant dérivé du contenu (#149).** `snapshotId` = `kh-<engagement>-<référentiel>-<12 premiers hex du checksum>`, comme l'instantané d'engagement (K11) : le même état donne le même identifiant, un contenu différent un autre. Avant, il portait l'horodatage de l'appel (`int(datetime.now().timestamp())`) : deux appels sur le même état donnaient deux identifiants, et le test de l'émetteur ne pouvait pas reconstruire un témoin. `createdAt` reste l'instant d'émission, **hors sceau** ; l'émetteur accepte un instant injecté (`now`) pour que le test reconstruise le témoin. L'enveloppe n'est donc pas strictement identique d'un appel à l'autre (`createdAt`) : seul le contenu scellé et l'identifiant le sont. Stocker les émissions pour rendre l'enveloppe entière idempotente (comme `POST …/exports`) n'est pas retenu ici.

**2. `allocated` exige une preuve (#148).** Un contrôle qu'aucun actif ne déclare couvrir est émis `identified`, plus `allocated`. Sur la base de démonstration (`nordwave-mcx-2027`, tous référentiels, mesuré le 2026-10-24), **40 des 91** contrôles étaient émis `allocated` avec `evidence: []` : une couverture que personne n'avait déclarée. Le Hub n'émet toujours jamais `verified`. `proposed` et `uncovered` sont le vocabulaire de l'instantané d'engagement (K17), pas celui de `ConformityData` (huit statuts du consommateur).

**3. Ce que le lecteur du Document Engine fait de cette sortie** (mesuré le 2026-10-24 sur `document-engine` `4a9361b`, avec son code ; `make verify-suite`).
- **Checksum : identique.** `computeSnapshotChecksum` du Document Engine recalcule exactement le `checksum` du Hub, sur le témoin de conformité et sur l'exemple d'instantané d'engagement. Les vecteurs `canonical-json` sont identiques octet pour octet.
- **Provenance : refusée.** `'sourceSystem' attendu 'tuleap', reçu 'knowledge-hub'` (ADR-DE-41 ; l'admission est l'objet de l'issue #152).
- **Ce qui refuserait ensuite, mesuré en expérience locale hors dépôt** (provenance et `ref` posées à la main) : la **version** (le lecteur oppose la majeure `4`, le Hub émet `2.0`), l'absence de **`ref`** (`RequirementRef`, requise en majeure 4 : issue #150) et la **source de preuve** : `evidence[].source` est un vocabulaire fermé (`architecture-studio`, `ip-flow-manager`, `document-engine`, `edm`, `tuleap`, `external-registry`) ; `knowledge-hub` n'en fait pas partie.
- La sortie du Hub n'est donc **pas** consommable aujourd'hui. Ce contrat ne la déclare pas branchée.

**Vérification** : `tests/contract/test_conformity_golden.py` (témoin reconstruit par l'émetteur, `tests/fixtures/suite/conformity-snapshot.golden.json`), `tests/unit/test_canonical_conformity_snapshot.py`, et `make verify-suite` (code du Document Engine, dépôt voisin ; code de sortie `3` quand il n'a rien pu comparer).

---

## 4. Oracles & Vecteurs de Test Partagés

Afin de garantir une interopérabilité sans faille entre implémentations Python et TypeScript, les vecteurs de référence suivants sont tenus à disposition dans le dépôt :
* **Vecteur de Test Canonique (`canonical-json v1` + SHA-256)** : [`tests/fixtures/canonical_conformity_vector.json`](../../tests/fixtures/canonical_conformity_vector.json)
* **Jeu d'Essai CCTP de Référence (Messagerie OIV)** : [`fixtures/rfp_messagerie_securisee.txt`](../../fixtures/rfp_messagerie_securisee.txt) (SHA-256: `792b9d332e8ccc589a2d74468d56bc761539542fc8d337a71d77854f87c258b5`)
