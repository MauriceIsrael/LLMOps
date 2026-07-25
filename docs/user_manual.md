# 📗 Manuel Utilisateur — Platform LLMOps (GraphRAG + FastMCP)

Ce manuel fournit toutes les instructions nécessaires pour installer, alimenter, faire tourner et tester la plateforme LLMOps neuro-symbolique.

---

## 📋 1. Prérequis & Installation

### Prérequis Système
- Linux / macOS / WSL2
- Python `>= 3.11`
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose (Optionnel, pour l'exécution conteneurisée)

### Clé d'API LLM
Le pipeline d'extraction LlamaIndex et les tests de non-régression sémantique (DeepEval) nécessitent une clé d'API OpenAI. Exposez-la dans votre environnement :
```bash
export OPENAI_API_KEY="sk-..."
```

### Installation du projet
```bash
# Se placer dans le dossier du projet
cd LLMOps

# Installer l'ensemble des dépendances Python via Poetry
poetry install
```

---

## 🔄 2. Ingestion de la Base de Connaissances (GraphRAG)

La base de connaissances se trouve dans le répertoire `data/kb/` (ADRs, Principes, Glossaire, Risques, etc.).

Pour exécuter le pipeline d'ingestion qui parse les fichiers Markdown, extrait les entités et relations avec LlamaIndex, puis alimente Kùzu DB :

```bash
poetry run ingest --kb-dir data/kb --db-path data/kuzu_db
```

### Options de la CLI d'ingestion :
- `--kb-dir PATH` : Chemin vers le répertoire source des documents Markdown (Par défaut: `data/kb`).
- `--db-path PATH` : Chemin de la base de données intégrée Kùzu (Par défaut: `data/kuzu_db`).
- `--force-rebuild` : Réinitialiser la base Kùzu avant l'ingestion.

---

## ⚡ 3. Démarrage du Serveur FastMCP

### Mode 1 : Démarrage standard (STDIO)
Pour lancer le serveur FastMCP directement en écoute sur les entrées/sorties standards (STDIO) :
```bash
poetry run mcp-server
```

### Mode 2 : FastMCP Dev Inspector (Interactif)
Pour tester interactivement les outils FastMCP dans une interface web dédiée :
```bash
poetry run fastmcp dev mcp_server/main.py
```
Une fois lancée, ouvrez l'URL indiquée (ex: `http://localhost:5173`) pour exécuter et visualiser les appels aux outils (`list_assets`, `get_decision_trail`, `get_glossary_term`, etc.).

---

## 🔌 4. Connexion aux Agents & IDEs

### Connexion à Claude Desktop / Cursor / Antigravity
Ajoutez le serveur MCP dans votre fichier de configuration (ex: `claude_desktop_config.json` ou la configuration MCP d'Antigravity) :

```json
{
  "mcpServers": {
    "llmops-architecture-kb": {
      "command": "poetry",
      "args": [
        "run",
        "mcp-server"
      ],
      "cwd": "/chemin/absolu/vers/LLMOps",
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

---

## 🤖 5. Guide d'Usage & Interaction avec l'Agent IA

Une fois le serveur MCP connecté à votre IDE ou Agent, vous pouvez interroger directement l'assistant en langage naturel.

### A. Exemples de Prompts Courants
- **Lister les décisions d'architecture** :
  > *"Peux-tu me lister les décisions d'architecture (ADR) présentes dans la base ?"*
- **Consulter le contenu d'un artefact** :
  > *"Affiche-moi le contenu complet de l'artefact ADR-0001."*
- **Chaîne de décision & Antériorité (`SUPERSEDES`)** :
  > *"Quel est l'historique et la chaîne de décision pour ADR-0001 ?"*
- **Consulter le Glossaire ou le Graphe Kùzu** :
  > *"Quelle est la définition du terme 'GraphRAG' ?"* ou *"Fais un résumé du graphe Kùzu DB."*

---

### B. Régénération Automatique d'un Document HLA (High-Level Architecture)
L'agent peut utiliser le template **`TPL-hla-section-map`** ([data/kb/templates/hla-section-map.md](file:///home/momo/Dev/LLMOps/data/kb/templates/hla-section-map.md)) pour régénérer la documentation HLA du système.

- **Comment procéder** :
  Demandez simplement dans le chat :
  > *"À partir du template HLA section map et de la base Kùzu DB, génère le document HLA complet avec la matrice de traçabilité et les diagrammes Mermaid."*

- **Distinction Socle Générique vs Instance Projet** :
  - **Le Socle Générique (Global KB)** : Les ADRs, principes, patterns et risques sont extraits automatiquement de Kùzu DB.
  - **L'Instance Projet (Contextuel)** : Les variables du projet (scope, questionnaires clients, deltas) sont lues depuis `projects/<nom_projet>/` ou demandées interactivement par l'agent.

---

### C. Gestion des Schémas ("Views as Code" / Draw.io)
Les schémas d'architecture ne sont pas dessinés manuellement : ils s'appuient sur le modèle **Views as Code**.
- Les générateurs Python dans `data/kb/views/generators/` (ex: `gen_drawio_set.py`) émettent dynamiquement les fichiers **`.drawio`** et **`.svg`** lors de la création d'un livrable projet.
- Dans le document Markdown HLA, l'agent génère les diagrammes au format **Mermaid.js** (pour affichage natif) et pointe vers les fichiers `.drawio` éditables émis pour le projet.

---

### D. Contribution & Règle de Cristallisation ("Promotion Rule")
Pour ajouter un nouveau contenu d'architecture :

1. **La Règle de Promotion** (définie dans [CONTRIBUTING.md](file:///home/momo/Dev/LLMOps/data/kb/CONTRIBUTING.md)) :
   - **1ère occurrence** → Le contenu est créé dans le projet spécifique (`projects/<nom_projet>/`).
   - **2ème occurrence (multi-projets)** → Le contenu est **cristallisé et promu** dans le socle générique (`decisions/`, `patterns/`, `principles/`), anonymisé de tout contexte client.

2. **Répartition des rôles (Architecte + Agent)** :
   - **L'Agent** : Vous pouvez lui dicter votre choix technique en langage naturel. Il rédige le Markdown avec le Frontmatter YAML conforme, classe l'artefact et relance `poetry run ingest` pour mettre à jour Kùzu DB.
   - **L'Architecte** : Définit le niveau de certitude (`confidence: verified / vendor-stated / assumed`) et valide la Pull Request (`agent-drafted`).

---


## 🧪 6. Exécution des Tests & Évaluations Sémantiques

### Tests Unitaires & Intégration
Exécuter la suite de tests unitaires (parsers, client Kùzu, outils MCP) :
```bash
poetry run pytest tests/unit tests/integration
```

### Evaluation de Non-Régression Sémantique (DeepEval)
Pour exécuter les métriques sémantiques (pertinence et fidélité des réponses de l'agent) :
```bash
poetry run deepeval test run tests/evals/deepeval/test_semantic_regression.py
```

### Benchmarking de Prompts (Promptfoo)
Pour tester des scénarios d'évaluation complémentaires avec Promptfoo :
```bash
npx promptfoo eval -c tests/evals/promptfoo/promptfooconfig.yaml
```

---

## 🐳 7. Exécution local via Docker Compose & Déploiement GCP Cloud Run

### A. Test local avec Docker Compose
Pour tester l'ensemble de la stack en local dans des conteneurs isolés :

```bash
# Lancer l'ingestion puis le serveur FastMCP en mode SSE (HTTP)
OPENAI_API_KEY="sk-..." docker compose -f docker/docker-compose.yml up --build
```
Le serveur FastMCP sera accessible sur `http://localhost:8000/sse`.

### B. Déploiement sur GCP Cloud Run (Serverless)

Cloud Run permet d'héberger le serveur FastMCP à moindre coût (scale-to-zero, facturation à l'usage).

1. **Construire et pousser l'image sur GCP Artifact Registry** :
   ```bash
   # Configurer votre projet GCP
   gcloud config set project VOTRE_PROJECT_ID

   # Pusher l'image optimisée
   gcloud builds submit --tag gcr.io/VOTRE_PROJECT_ID/llmops-mcp-server:latest -f docker/Dockerfile.cloudrun .
   ```

2. **Déployer sur Cloud Run** :
   ```bash
   gcloud run deploy llmops-mcp-server \
     --image gcr.io/VOTRE_PROJECT_ID/llmops-mcp-server:latest \
     --platform managed \
     --region europe-west1 \
     --allow-unauthenticated \
     --set-env-vars LLMOPS_TRANSPORT=sse,OPENAI_API_KEY=sk-...
   ```


---

## ❓ 8. Résolution des Problèmes Fréquents (FAQ)


| Problème | Cause Possible | Solution |
|---|---|---|
| `Lock error` sur Kùzu DB | Plusieurs processus tentent d'écrire en même temps dans Kùzu DB | Assurez-vous que le job d'ingestion est terminé avant de démarrer le serveur MCP en écriture |
| `AuthenticationError: OPENAI_API_KEY missing` | La variable d'environnement n'est pas définie | Exécutez `export OPENAI_API_KEY="sk-..."` avant de lancer les commandes |
| Outil MCP non trouvé par l'agent | Mauvais fichier de config MCP dans l'IDE | Vérifiez le chemin absolu `cwd` dans la configuration MCP de l'IDE |
