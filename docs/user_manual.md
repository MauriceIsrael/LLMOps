# Manuel Utilisateur — Plateforme LLMOps (GraphRAG + FastMCP + Élicitation)

Ce manuel fournit toutes les instructions nécessaires pour installer, alimenter, utiliser, visualiser et partager la plateforme LLMOps (GraphRAG, FastMCP, LadybugDB) et son système d'élicitation collaboratif.

---

## 1. Prérequis & Installation

### Prérequis Système

- Linux / macOS / WSL2
- Python `>= 3.11`
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose (Optionnel)

### Clé d'API LLM

Exposez votre clé OpenAI pour l'extraction LlamaIndex :

```bash
export OPENAI_API_KEY="sk-..."
```

### Installation

```bash
cd LLMOps
poetry install
```

---

## 2. Ingestion & Migration des Bases Graphiques (LadybugDB / ADR-0015)

```bash
# Ingestion des documents Markdown (ADRs, Glossaire, Principes) et migration physique vers LadybugDB
poetry run python -m pipelines.ingestion.migrate_adr0015

# (Optionnel) Spécifier le moteur graphique explicitement via la variable d'environnement GRAPH_BACKEND
GRAPH_BACKEND=ladybug poetry run python -m pipelines.ingestion.migrate_adr0015
```

- Ingestion des fichiers Markdown (`.md`) et des spécifications YAML (`.yaml` / `.yml`).
- Structure physique ADR-0015 créée automatiquement : `data/knowledge.kuzu` (`database.lbug`) et `data/engagements/nordwave-mcx-2027.kuzu`.
- Génération automatisée de la documentation du schéma : `poetry run python -m pipelines.ingestion.generate_schema_doc`.

---

## 3. Validation de Non-Régression & Tests

```bash
# Exécution de l'ensemble de la suite de tests déterministes (78 unitaires, 20 contrats, 18 équivalence)
poetry run pytest -m deterministic -v

# Exécution des benchmarks et tests d'évaluation sémantique DeepEval
poetry run python tests/bench/harness.py
poetry run pytest tests/bench/test_bench.py -v
```

### Visualiseur Web local

```bash
poetry run visualize
```

*Ouvrez [graph_explorer.html](graph_explorer.html) dans votre navigateur.*

### Visualiseur Web GCP Cloud Run en direct

`https://llmops-mcp-server-344571265365.europe-west1.run.app/visualize?token=demo-public-2026-08`

---

## 4. Élicitation Collaborative (Chatbot Inversé)

Le système d'élicitation (`elicit`) permet à une équipe d'architectes de compléter déterministement les dossiers d'architecture.

### A. Mode CLI (Hors-ligne / Démo avec drapeau d'usurpation `--as`)

Grâce au drapeau d'usurpation `--as <login>` (`--as alice`, `--as bob`, `--as charlie`), **une seule personne peut simuler l'interaction de 3 personnes** sans créer de comptes GitHub !

```bash
# 1. Détecter les manques du projet et poser les questions dans la boîte aux lettres
poetry run elicit scan --engagement nordwave-mcx-2027

# 2. Réponse d'Amina (mcx-service-architect) via une fiche Markdown ou CLI
poetry run elicit answer Q-0001 --from-file artifacts/nordwave-mcx-2027/mailbox/Q-0001.md --as amina

# 3. Validation de la proposition d'extraction (Interrupt / Human-in-the-loop)
poetry run elicit confirm Q-0001 --accept

# 4. Observer la trajectoire d'un sujet (Level Gate & historisation)
poetry run elicit trajectory --engagement nordwave-mcx-2027 --subject mcx-services

# 5. Rétrogradation de maturité (Demotion non-monotone) si remise en cause
poetry run elicit demote --engagement nordwave-mcx-2027 --subject floor-control --to-level L2_decomposed --by sofia --reason "Révision nécessaire"

# 6. Soumettre une contribution externe terrain (double confirmation)
poetry run elicit contribute --engagement nordwave-mcx-2027 --file demo/answers/contribution.md --as rui

# 7. Arbitrage par Sofia (chief-architect) via --as sofia
poetry run elicit arbitrate C-0001 --keep S-0001 --reason "Arbitrage MCX service layer au site" --as sofia

# 8. Assembler le document final (projects/nordwave-mcx-2027/document.md)
poetry run elicit assemble --engagement nordwave-mcx-2027
```

### B. Mode Test d'Intégration Référent (Scénario Nordwave MCX v2)

Pour exécuter la démonstration automatisée complète couvrant les 6 phases et 18 tests d'élicitation :

```bash
poetry run pytest tests/integration/test_scenario_nordwave_mcx_v2.py -v
```

---

## 5. Comment utiliser la Plateforme

### Option 1 : Partager l'accès au Serveur MCP (Claude Desktop / Cursor / Antigravity / VS Code)

Transmettez simplement cet extrait de configuration à vos collègues pour qu'ils l'ajoutent dans leur fichier `mcp_config.json` local :

```json
{
  "mcpServers": {
    "llmops-architecture-kb": {
      "url": "https://llmops-mcp-server-344571265365.europe-west1.run.app/sse",
      "headers": {
        "Authorization": "Bearer demo-public-2026-08"
      }
    }
  }
}
```

*Vos collègues peuvent alors interroger directement la base d'architecture en langage naturel depuis leur IDE.*

---

### Option 2 : Partager le Visualiseur Web Interactif du Graphe

Transmettez ce lien direct à vos collègues pour qu'ils explorent la base de connaissances sans rien installer :
`https://llmops-mcp-server-344571265365.europe-west1.run.app/visualize?token=demo-public-2026-08`

---

### Option 3 : Partager l'Élicitation Collaborative sur GitHub Issues (Sans ligne de commande pour vos collègues !)

Vos collègues n'ont **rien à installer** sur leur poste. Ils répondent directement dans leur navigateur sur GitHub !

1. **Déclarer vos collaborateurs dans le fichier d'annuaire `projects/demo-2026/roster.yaml`** :

   ```yaml
   - login: alice-gh
     name: Alice
     roles: [cloud-architect]
   - login: bob-gh
     name: Bob
     roles: [storage-expert]
   - login: charlie-gh
     name: Charlie
     roles: [chief-architect]
   ```

2. **Génération automatique des Issues GitHub** :
   Lorsqu'un scan tourne, le système crée une Issue GitHub privée avec la fiche Markdown complète, le tag du rôle assigné (ex: `role:cloud-architect`) et la commande pré-remplie `/answer Q-0001 --text "..."`.

3. **Vos collègues répondent par simple commentaire GitHub** :
   - Alice écrit un commentaire `/answer ...` puis `/confirm`.
   - Bob écrit un commentaire `/answer ...` pour proposer une alternative.
   - Charlie résout le conflit en commentant `/arbitrate keep S-0001 --reason "..."`.

---

## 6. Ingestion de Solutions Externes (DOCX, PDF, Markdown) & Audit Automatisé

Vous pouvez confronter n'importe quel dossier d'architecture existant (dossier Word `.docx`, spécification PDF ou fichier Markdown) au Blueprint de référence et aux contrôles réglementaires (NIS2, 3GPP) :

```bash
# Ingestion et analyse des manques (gaps G1 à G4) en une seule commande :
poetry run python scripts/ingest_solution_doc.py data/project/netdevops/netdevops_mcx_architecture_document_v1.3.docx --engagement netdevops-2026 --scan
```

### Ce que produit cette commande :
1. **Extraction structurée** : Découpage automatique des chapitres, paragraphes et tableaux sans dépendance externe requise pour Word.
2. **Alignement Blueprint** : Rapprochement de chaque section avec les attendus formels et les exigences de sécurité (ex: NIS2 Article 21).
3. **Génération du Dossier** : Création du draft d'architecture dans `projects/<engagement>/draft.md`.
4. **Scan des Lacunes** : Détection immédiate des sections vides (G1), sujets non cadrés (G2), paramètres non spécifiés (G3) et contrôles de conformité non satisfaits (G4).

---

## 7. Script de Publication Automatisée sur GCP Cloud Run

Pour déployer en toute sécurité une nouvelle version du serveur FastMCP sur Google Cloud Run :

```bash
./scripts/deploy_gcp.sh
```

Le script vérifie la propreté Git, exécute les vérifications de pré-vol locales (Ruff & tests de contrat), soumet le build Docker allégé à Cloud Build, et effectue un health check automatique sur l'URL de production.

---

## 8. Audit de Staffing & Gestion des Compétences du Projet

Le système audite l'adéquation entre l'équipe mobilisée et les exigences techniques du Blueprint d'architecture :

### 8.1 Auditer la couverture des compétences
```bash
poetry run elicit audit-skills --engagement nordwave-mcx-2027
```
Affiche la matrice complète de couverture, le taux global (ex: `88.9%`), les compétences critiques non pourvues, et l'**Index de risque de staffing** (*Faible / Modéré / Critique*).

### 8.2 Administrer l'équipe et résoudre les manques (Gap G5)
* **Affecter un nouveau collaborateur interne :**
  ```bash
  poetry run elicit staff assign --engagement nordwave-mcx-2027 --user julien --role cloud-architect --skills "SKL-KUBE-TELCO,SKL-AUTO-GITOPS"
  ```
* **Enregistrer une montée en compétence / certification :**
  ```bash
  poetry run elicit staff add-skill --engagement nordwave-mcx-2027 --user sofia --skill SKL-CRYPTO-HSM --level expert --evidence "Certification ANSSI 2026"
  ```
* **Contractualiser une expertise ou assistance technique externe :**
  ```bash
  poetry run elicit staff contract-expertise --engagement nordwave-mcx-2027 --skill SKL-CRYPTO-HSM --provider "Cabinet Cryptologique Thalix" --ref "PO-2026-904"
  ```

---

## 9. Analyseur d'Appels d'Offres (RFP / CCTP) & Dream Team Matrix

En phase d'avant-vente, analysez un cahier des charges client (Word `.docx`, `.pdf`, ou `.md`) pour obtenir immédiatement les compétences requises, les référentiels cibles et le profil d'équipe recommandé :

```bash
poetry run python scripts/analyze_rfp.py data/project/netdevops/netdevops_mcx_architecture_document_v1.3.docx
```

### Résultats générés :
* **Référentiels détectés** : NIS2, SecNumCloud, 3GPP, ISO 27001.
* **Compétences classées** : Intensité (Haute / Moyenne / Ponctuelle), séniorité attendue (Senior, Expert).
* **Dream Team Staffing Matrix** : Rôles recommandés, charges estimées (en ETP) et missions clés.
* **Option d'export** : `--output rapport-staffing.md` ou `.json`.

---

## 10. Suggestions, Harvest REX & Notifications Discord

Lorsqu'un projet valide de nouvelles pratiques ou limitations constructeurs, le moissonnage REX permet de notifier instantanément le propriétaire de la base :

```bash
# Moissonner les candidats REX d'un projet et notifier Maurice sur Discord :
poetry run elicit harvest --engagement nordwave-mcx-2027
```

Les notifications sont transmises sous forme d'**Embed riche sur Discord** (titre, auteur, contexte projet, raison et extrait Markdown de la proposition) et archivées dans `data/suggestions/`.

