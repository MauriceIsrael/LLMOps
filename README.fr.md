# LLMOps — Base de Connaissances d'Architecture Interrogeable en MCP

> Base de connaissances d'architecture interrogeable en MCP : chaque énoncé porte sa confiance et sa maturité, pour que vos générateurs de documents sachent ce qu'ils ont le droit d'affirmer.

[English Version (README.md)](README.md)

---

## Démarrage Rapide & Configuration Client MCP

Connectez n'importe quel client MCP (Claude Desktop, Cursor, Antigravity, VS Code) en 30 secondes.

### 1. Connexion Distante (GCP Cloud Run Serverless SSE)

Ajoutez la configuration suivante dans votre client MCP (ex: `claude_desktop_config.json` ou paramètres Cursor) :

```json
{
  "mcpServers": {
    "llmops-remote": {
      "url": "https://llmops-mcp-server-344571265365.europe-west1.run.app/sse",
      "headers": {
        "Authorization": "Bearer demo-public-2026-08"
      }
    }
  }
}
```

> **Avertissement Instance de Démonstration Publique :** Expose à la fois le plan Connaissances et le plan Engagement (scopé strictement sur l'engagement de référence de démonstration). Lecture seule, taux limité, pas de SLA. Le jeton ci-dessus (`demo-public-2026-08`) est intentionnellement public et renouvelé périodiquement. Ne l'utilisez pas pour des données privées.

### 2. Connexion Locale (STDIO via Poetry)

```json
{
  "mcpServers": {
    "llmops-knowledge": {
      "command": "poetry",
      "args": ["run", "mcp-server-knowledge"],
      "cwd": "/chemin/vers/LLMOps"
    },
    "llmops-engagement": {
      "command": "poetry",
      "args": ["run", "mcp-server-engagement"],
      "cwd": "/chemin/vers/LLMOps"
    }
  }
}
```

### 3. Démonstration en Une Commande

```bash
make demo
make demo-check
```

**Nombres de Nœuds Attendus (`make demo-check`) :**
- **Plan de Connaissances (`data/knowledge.kuzu`)** : `Asset`: ~46 nœuds, `GlossaryTerm`: ~10 nœuds.
---

## Points Clés & Différenciateurs

1. **Cœur Déterministe et Auditable (0 Coût LLM Serveur)**  
   Aucun appel LLM non-déterministe côté serveur. La base est orchestrée par une base graphe typée (LadybugDB). Les règles d'élicitation, de level gate et de détection de contradictions reposent sur une logique symbolique pure.
2. **Gestion de l'Épistémique et de la Confiance**  
   Chaque énoncé architectural porte explicitement sa confiance (`verified`, `designed`, `vendor-stated`, `stated-by-client`, `assumed`) et son niveau de maturité (`L0_named` à `L4_specified`). Les documents générés indiquent s'ils sont provisoires (`is_provisional: true`, `unripe_subjects`, `open_conflicts`).
3. **Isolation Physique Dual-Plane (ADR-0015)**  
   Les connaissances transverses (`data/knowledge.lbug`) sont strictement séparées des engagements projets (`data/engagements/<id>.lbug`).
4. **Canal d'Instantané Scellé (Sealed Snapshot)**  
   Publication d'exports JSON scellés par SHA-256 (`fixtures/sealed_snapshot.json` ou `GET /snapshot/latest`) avec identifiants typés (`decision:ADR-0014`, `principle:P-002`) et index d'applicabilité pour une intégration résiliente et sans latence (ex. *Architecture Studio*).
5. **Référentiels Réglementaires TELCO MCX Souverains (14 Frameworks, 53 Contrôles)**  
   Couverture complète de conformité technique sur les normes européennes et critiques : NIS2, CER (Résilience des entités critiques UE 2022/2557), CRA (Cyber Resilience Act UE 2024/2847), RGPD, GSMA (eSIM SGP.22/32, Central EIR, SAS EAL4+), 3GPP Rel-18 (MCX, NEF, SCAS/NESAS, MDA AIOps), ITIL v4 / FCAPS O&M, Résilience Télécom (Datacenters Tier IV, sync PTP G.8275.1, holdover Rubidium >30j), et Terminaux Tactiques PPDR (Bande 68/28 ECC, TETRA DMO, MIL-STD-810H, ATEX, CEM véhicule ISO 11451/UN R2144).
6. **Déstructeur de RFP & Générateur de Zero-Draft HLD Bilingue (FR / EN)**  
   Déconstruction atomique des cahiers des charges (`shred-rfp`), calcul de matrice triangulaire de conformité et génération instantanée du dossier d'architecture d'avant-vente (`zero-draft-hld`) en français ou en anglais sans écart résiduel. Modèles de livrables normalisés disponibles dans `templates/HLD-zero-draft-template.md` (FR) et `templates/HLD-zero-draft-template.en.md` (EN).
7. **Paquet de Doctrine & Juge d'Option (contrat 1.1)**  
   `get_doctrine_context` / `GET /api/knowledge/context` renvoie la doctrine applicable à un sujet (principes actifs, contrôles réglementaires exigés, patterns, ADR) avec des extraits bornés ; `check_option` / `POST /api/knowledge/check` juge une option contre les clauses de contrôle structurées `checks` de la doctrine (`supports` / `violates` / `unassessed`, avec citations). Les deux sont 100 % déterministes — aucun LLM côté serveur. Évaluation : `make eval-check`.
8. **Cycle d'Enrichissement de la Base (contrat 1.2)**  
   Toute connaissance nouvelle passe par une file de candidats persistée (`/api/knowledge/candidates`, `submit_kb_candidate`…), des contrôles déterministes (gabarit, références, doublons, anonymisation, conflits de doctrine, contenu LLM non relu), un routage vers le propriétaire du domaine (`data/kb/owners.yaml`) et une revue humaine (seconde revue pour un principe), avant que `kb promote` / `kb publish` ne l'écrivent et ne la scellent. La confiance est calculée à partir des preuves, jamais de l'auteur.
9. **Architecture Double-Mode & Contrat v1 Architecture Suite**  
   Fourniture simultanée d'endpoints REST synchrones (`/api/rfp/*`, `/api/compliance/*`, `/api/knowledge/*`, `/api/skills/*`) pour les interfaces interactives et CLI, et de snapshots canoniques scellés (`latest.json`) pour les sas d'admission hors-ligne (ADR-SUITE-05). Tous les contrats respectent une provenance stricte (`sourceSystem: "knowledge-hub"`), un scellement SHA-256 canonique et le principe de résilience *Fail Loud*.

---

## Développement & Tests

```bash
# Suite de tests (contrat, unitaires, intégration)
make test

# Lint (mypy + ruff)
make lint

# Contrôle local rapide : lint + contrat d'interfaces gelées + tests unitaires
make verify

# Installer le hook git pre-push qui exécute `make verify`
make hooks

# Scénarios de bout en bout de la démo de référence (examples/) et garde-fou des noms de projet
make test-e2e
make check-names

# Ingestion hors ligne d'un référentiel et couverture
poetry run kb ingest-framework --framework NIS2 --version 2022/2555 --source <texte officiel>
poetry run kb review-sheet --framework NIS2 && poetry run kb apply-review data/staging/NIS2/2022-2555/review_sheet.csv
poetry run kb declare-coverage --framework NIS2 --by @handle-expert
poetry run kb coverage-report   # docs/COVERAGE.md

# Cycle des candidats de la base (mainteneurs)
poetry run kb list --status in_review
poetry run kb promote CAND-20261001-0007
poetry run kb publish
poetry run kb remind   # à planifier par cron
```

> **Aucun projet n'est codé en dur.** Les outils, routes et commandes `elicit` qui ont besoin
> d'un engagement ou d'un blueprint les reçoivent explicitement ou via `LLMOPS_ENGAGEMENT` /
> `LLMOPS_BLUEPRINT` (environnement ou `.env` ; `make demo`, le Dockerfile et `cloudbuild.yaml`
> les positionnent pour la démo de référence). La démo de référence vit dans
> [`examples/`](examples/README.md).

---

## Liens vers la Documentation

- **[Couverture réglementaire](docs/COVERAGE.md)** : couverture de chaque référentiel par la base (manifestes, exigences manquantes).
- **[Versionnement](docs/VERSIONING.md)** et **[Politique de dépréciation](docs/DEPRECATION.md)** : garanties du contrat `1.x`, formes d'interfaces gelées (`tests/contract/frozen/`), signaux de dépréciation. La partie engagement (élicitation / arbitrage) est **dépréciée depuis la 1.13** au profit d'Archinex : voir le [guide de migration](docs/migration-archinex.md).
- **[Contrat d'API Knowledge Hub v1](docs/contracts/knowledge-hub-api-v1.md)** : Spécification contractuelle pour l'Architecture Suite (`requirements-intake`, `document-engine`, `Document-studio`, `WBS-engine`).
- **[Guide d'Intégration Tiers](docs/THIRD-PARTY-INTEGRATION-GUIDE.md)**
- **[Spécification d'Interface Externe (INTERFACE.md)](docs/INTERFACE.md)**
- **[Guide d'Alignement Épistémique (EPISTEMIC-ALIGNMENT.md)](docs/EPISTEMIC-ALIGNMENT.md)**
- **[Spécification du Schéma Graphe (SCHEMA.md)](docs/SCHEMA.md)**
- **[Architecture Logicielle (ADR-0014 / ADR-0015)](docs/architecture.md)**
- **[Manuel Utilisateur](docs/user_manual.md)**

---

## Licence

Sous licence MIT. Voir `LICENSE` pour plus de détails.
